# タスク設計書: ACC仕組み可視化UI Phase 6 実装

最終更新: 2026-02-08
- ステータス: 完了(done)
- 作成者: Codex
- レビュー: shogohasegawa
- 対象コンポーネント: backend / frontend / docs
- 関連: `docs/blue-print/arxiv-2601.11653.md`, `docs/task-designs/20260208193504_openai-chat-ui-phase5.md`, `docs/api/chat-messages-post.md`
- チケット/リンク: 該当なし

## 0. TL;DR
- チャットUIに「ACCがどう状態更新して応答したか」を表示するため、`POST /api/chat/messages` のレスポンスにメカニズム情報を追加する。
- 具体的には、想起候補数・採用候補数・CCS要素（goal/constraints/gist/predictive cue など）を返し、UIでターンごとに可視化する。
- 既存のチャット機能は維持し、追加フィールドは後方互換（既存クライアントは無視可能）とする。
- API仕様書とテストを同時更新し、実装とドキュメントを同期させる。

## 1. 背景 / 課題
- 現在の UI は「ユーザー入力と最終応答」しか見えず、ACC 論文で重要な「Recall → Qualification → Commit → Decide」の流れが把握しにくい。
- 実利用時に ACC の挙動理解・デバッグ・説明を行うためには、ターンごとの内部状態要約が必要。
- コアロジックには `ACCTurnResult` が存在し必要情報は取得可能なため、API と UI の出力拡張で対応できる。

## 2. ゴール / 非ゴール
### 2.1 ゴール
- `POST /api/chat/messages` 成功レスポンスに ACC 可視化情報を追加する。
- UI に ACC メカニズムパネルを追加し、各ターンで次を表示する:
  - 想起候補数
  - 採用候補数
  - 推定メモリトークン
  - CCS の主要項目（semantic gist / goal / constraints / predictive cue / uncertainty / retrieved artifacts）
- 表示はチャット応答の下でターン単位に確認できるようにする。

### 2.2 非ゴール
- 本格的な監視ダッシュボード（時系列グラフ、永続ログ検索）。
- 新規 API エンドポイント追加（今回は既存 `POST /api/chat/messages` 拡張のみ）。
- CCS 全文の永続化や外部DB保存。

## 3. スコープ / 影響範囲
- 変更対象:
  - `src/acc/application/use_cases/chat_session.py`
  - `src/acc/adapters/inbound/http/schemas.py`
  - `src/acc/adapters/inbound/http/app.py`
  - `src/acc/adapters/inbound/http/static/index.html`
  - `tests/unit/test_chat_session.py`
  - `tests/unit/test_http_chat_api.py`
  - `docs/api/chat-messages-post.md`
  - `docs/api/index.md`（更新日・要約調整）
- 影響範囲: API レスポンス構造、ブラウザUI表示、単体/結合テスト。
- 互換性: 既存フィールドは維持し追加のみのため後方互換。
- 依存関係: 新規ライブラリ追加なし。

## 4. 要件
### 4.1 機能要件
- `ChatReply` に ACC 可視化用情報を保持する。
- `ChatMessageResponse` に `mechanism` オブジェクトを追加する。
- `mechanism` は次の情報を含む:
  - `recalled_artifact_count`（int）
  - `qualified_artifact_count`（int）
  - `committed_state`（CCS主要項目）
- UI は送信成功ごとに、該当ターンの `mechanism` 内容を人が読める形で表示する。

### 4.2 非機能要件 / 制約
- 既存の API エラー仕様（400/404/502/503）は維持する。
- OpenAI API キー不要の単体/結合テストを維持する（in-memory アダプタを利用）。
- `ruff` / `mypy` / `pytest` をすべて通過させる。

## 5. 仕様 / 設計
### 5.1 全体方針
- ACC コアロジックは変更せず、既存 `ACCTurnResult` から取得できる情報を application 層で整形して返す。
- inbound adapter では DTO 変換のみを行い、UI は API レスポンスを表示する責務に限定する。
- 可視化は「理解しやすさ優先」で、CCS全文ではなく主要項目の簡約表示に留める。

### 5.2 変更点一覧
| 対象 | 変更内容 | 影響 | 備考 |
| --- | --- | --- | --- |
| `src/acc/application/use_cases/chat_session.py` | `ChatReply` に mechanism 情報を追加 | APIレスポンス元データ拡張 | `ACCTurnResult` を利用 |
| `src/acc/adapters/inbound/http/schemas.py` | `ChatMessageResponse` に mechanism schema を追加 | API契約変更（追加） | 後方互換 |
| `src/acc/adapters/inbound/http/app.py` | response mapping に mechanism を追加 | API出力反映 | 既存エラーハンドリング維持 |
| `src/acc/adapters/inbound/http/static/index.html` | ACCメカニズム表示パネル追加 | UX向上 | チャットUIと同時表示 |
| `tests/unit/test_chat_session.py` | mechanism 情報の検証追加 | 回帰防止 | |
| `tests/unit/test_http_chat_api.py` | APIレスポンスの mechanism 検証追加 | 回帰防止 | |
| `docs/api/chat-messages-post.md` | 追加フィールドを仕様反映 | 仕様同期 | api-spec-sync相当運用 |
| `docs/api/index.md` | 更新履歴更新 | 仕様同期 | |

### 5.3 詳細
#### API
- 既存: `session_id`, `turn_id`, `reply`, `memory_tokens`
- 追加: `mechanism`
  - `recalled_artifact_count: int`
  - `qualified_artifact_count: int`
  - `committed_state: { semantic_gist, goal_orientation, constraints[], predictive_cue[], uncertainty_signal, retrieved_artifacts[] }`

#### UI
- レイアウトを 2 カラム化（チャット + ACC 状態）。
- 各ターン応答時に、対応する mechanism カードを追加。
- 表示コピーは ACC ループ語彙を使い、論文の流れを追えるようにする。

#### データモデル / 永続化
- 永続化方式は変更なし（in-memory session）。
- mechanism はそのターンのレスポンスとしてのみ返却する。

#### 設定 / 環境変数
- 追加・変更なし。

### 5.4 代替案と不採用理由
- 代替案A: 新規 `GET /api/chat/sessions/{id}/state` を追加して状態取得する。
  - 不採用理由: フロント実装と API 複雑性が増え、今回は「理解用の即時表示」が目的のため過剰。
- 代替案B: UI 側で返信文のみから擬似的に内部状態を推定表示する。
  - 不採用理由: 実際の ACC 状態と乖離し、説明責任を満たせない。

## 6. 移行 / ロールアウト
- 追加フィールド方式のため段階的移行不要。
- ロールバック条件: API契約更新により既存テストまたは UI が不安定化した場合。
- ロールバック手順: `mechanism` 追加部分を revert し、Phase 5 の API/UI に戻す。

## 7. テスト計画
- 単体:
  - `ChatSessionUseCase.send_message()` が mechanism 情報を返すことを検証。
- 結合:
  - `POST /api/chat/messages` のレスポンスに `mechanism` が含まれることを検証。
- 手動:
  - UI で 2 ターン送信し、各ターンで mechanism 表示が更新されることを確認。
- LLM/外部依存:
  - CI は in-memory アダプタのみ使用し OpenAI 依存なし。
- 合格条件:
  - `uv run ruff format --check src tests`
  - `uv run ruff check src tests`
  - `uv run mypy src tests`
  - `uv run pytest -q`
  - ブラウザ手動確認で mechanism 可視化を確認。

## 8. 受け入れ基準
- `POST /api/chat/messages` 成功レスポンスに `mechanism` が含まれる。
- UI 上で ACC の 4段階（Recall/Qualification/Commit/Decide）の理解に必要な情報が確認できる。
- 既存チャット操作（セッション作成・送信・応答表示）が維持される。
- API ドキュメントが実装差分に追随している。

## 9. リスク / 対策
- リスク: CCS 情報をそのまま表示すると情報量過多になり読みづらい。
- 対策: 主要項目に限定し、配列は件数とリスト表示を併用する。
- リスク: API レスポンス肥大化。
- 対策: 今回はテキスト短尺データのみとし、全文ログや生 Artifact 内容は返さない。

## 10. オープン事項 / 要確認
- なし。

## 11. 実装タスクリスト
- [x] `ChatReply` / API schema に mechanism 追加
- [x] `app.py` のレスポンス変換を更新
- [x] `index.html` に ACC 可視化パネルを追加
- [x] 単体/結合テスト更新
- [x] API ドキュメント更新
- [x] 品質コマンド実行

## 12. ドキュメント更新
- [ ] `README.md`（必要に応じて）
- [ ] `AGENTS.md`（必要に応じて）
- [x] `docs/task-designs/20260208200436_acc-mechanism-visualization-ui-phase6.md`
- [x] `docs/api/chat-messages-post.md`
- [x] `docs/api/index.md`

## 13. 承認ログ
- 承認者: shogohasegawa
- 承認日時: 2026-02-08 20:05
- 承認コメント: OK

## 実装開始条件
- [x] ステータスが `承認済み(approved)` である
- [x] 10. オープン事項が空である
- [x] 受け入れ基準とテスト計画に合意済み
