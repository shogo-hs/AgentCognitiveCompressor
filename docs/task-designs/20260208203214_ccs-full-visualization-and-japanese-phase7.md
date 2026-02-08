# タスク設計書: CCS全量可視化と日本語管理 Phase 7 実装

最終更新: 2026-02-08
- ステータス: 完了(done)
- 作成者: Codex
- レビュー: shogohasegawa
- 対象コンポーネント: backend / frontend / docs
- 関連: `docs/task-designs/20260208200436_acc-mechanism-visualization-ui-phase6.md`, `docs/blue-print/arxiv-2601.11653.md`, `docs/api/chat-messages-post.md`
- チケット/リンク: 該当なし

## 0. TL;DR
- 現状 UI は CCS の主要項目のみ表示で、`episodic_trace` / `focal_entities` / `relational_map` が欠けている。
- `POST /api/chat/messages` の `mechanism.committed_state` を CCS 全9フィールドに拡張し、UI で全量を表示する。
- OpenAI 圧縮プロンプトと補助アダプタを調整し、CCS の文言を日本語で管理する方針を明示する。
- API ドキュメントとテストを更新し、実装と仕様の同期を維持する。

## 1. 背景 / 課題
- ユーザー要望: CCS が UI に全量表示されること、および CCS を日本語で管理すること。
- Phase 6 時点では `committed_state` が部分表示であり、CCS 全体の監査・説明に不足がある。
- OpenAI 圧縮プロンプトが英語中心のため、CCS 生成言語が英語へ寄る可能性がある。

## 2. ゴール / 非ゴール
### 2.1 ゴール
- API レスポンスで CCS 全9フィールドを返す。
- UI で CCS 全フィールドを表示する。
- CCS テキスト（要約・目標・制約など）を日本語生成に寄せるプロンプト制約を追加する。
- in-memory 実装でも日本語ベースの既定語彙へ揃える。

### 2.2 非ゴール
- 多言語切替機能の追加。
- 過去ターン CCS の永続保存や検索機能。
- 既存 API エンドポイントの追加。

## 3. スコープ / 影響範囲
- 変更対象:
  - `src/acc/application/use_cases/chat_session.py`
  - `src/acc/adapters/inbound/http/schemas.py`
  - `src/acc/adapters/inbound/http/app.py`
  - `src/acc/adapters/inbound/http/static/index.html`
  - `src/acc/adapters/outbound/openai_chat_adapters.py`
  - `src/acc/adapters/outbound/in_memory_acc_components.py`
  - `tests/unit/test_chat_session.py`
  - `tests/unit/test_http_chat_api.py`
  - `docs/api/chat-messages-post.md`
  - `docs/api/index.md`
- 影響範囲: API レスポンス項目、UI 表示内容、CCS 生成言語、テスト期待値。
- 互換性: `mechanism` 以下への追加のみで後方互換。
- 依存関係: 新規ライブラリ追加なし。

## 4. 要件
### 4.1 機能要件
- `committed_state` に次を含める:
  - `episodic_trace`
  - `semantic_gist`
  - `focal_entities`
  - `relational_map`
  - `goal_orientation`
  - `constraints`
  - `predictive_cue`
  - `uncertainty_signal`
  - `retrieved_artifacts`
- UI は上記9項目をターンごとに表示する。
- OpenAI 圧縮プロンプトに「CCS の自然言語フィールドは日本語で出力」を明記する。
- in-memory 圧縮アダプタの既定語彙（goal/predictive/uncertainty）を日本語化する。

### 4.2 非機能要件 / 制約
- 既存エラーハンドリング（400/404/502/503）を維持する。
- `ruff` / `mypy` / `pytest` を通す。
- 秘密情報ファイル（`.env*`）は変更・コミットしない。

## 5. 仕様 / 設計
### 5.1 全体方針
- domain の `CompressedCognitiveState` は既存のまま利用し、API DTO を全量化する。
- UI は mechanism カードの表示行を増やし、全フィールドを確認可能にする。
- 言語方針は OpenAI compressor 側で拘束し、policy 応答とは分離する。

### 5.2 変更点一覧
| 対象 | 変更内容 | 影響 | 備考 |
| --- | --- | --- | --- |
| `src/acc/application/use_cases/chat_session.py` | `ChatCommittedStateSummary` を CCS 全量化 | APIレスポンス元データ拡張 | |
| `src/acc/adapters/inbound/http/schemas.py` | `CommittedStateResponse` に全フィールド追加 | API契約拡張 | 後方互換 |
| `src/acc/adapters/inbound/http/app.py` | response mapping を全量化 | API出力反映 | |
| `src/acc/adapters/inbound/http/static/index.html` | CCS 全項目表示に拡張 | UX/可観測性向上 | |
| `src/acc/adapters/outbound/openai_chat_adapters.py` | 日本語管理の出力制約を追加 | CCS言語統制 | |
| `src/acc/adapters/outbound/in_memory_acc_components.py` | 既定語彙を日本語へ変更 | テスト整合 | |
| `tests/unit/test_chat_session.py` | 全量フィールドと日本語期待を検証 | 回帰防止 | |
| `tests/unit/test_http_chat_api.py` | APIレスポンス全量検証追加 | 回帰防止 | |
| `docs/api/chat-messages-post.md` | `committed_state` の全項目を反映 | 仕様同期 | |
| `docs/api/index.md` | 変更履歴更新 | 仕様同期 | |

### 5.3 詳細
#### API
- `mechanism.committed_state` を CCS 全量にする。
- 既存項目はそのまま維持し、追加配列項目を返す。

#### UI
- `Commit` 表示に以下を追加:
  - `episodic_trace`
  - `focal_entities`
  - `relational_map`
- 既存表示順を保ちつつ、情報過多を避けるため配列は短く整形表示する。

#### データモデル / 永続化
- 永続化方式変更なし（in-memory）。
- 返却データのみ拡張。

#### 設定 / 環境変数
- 追加・変更なし。

### 5.4 代替案と不採用理由
- 代替案A: UI だけで `reply` から CCS っぽい表示を再構成する。
  - 不採用理由: 実 CCS と乖離し監査性を損なう。
- 代替案B: CCS 全量表示を新規 API に分離する。
  - 不採用理由: 今回の要求はチャット画面で即時確認できることが主目的であり過剰。

## 6. 移行 / ロールアウト
- 追加フィールド中心のため段階的移行不要。
- ロールバック条件: UI 可読性劣化やテスト不安定化が発生した場合。
- ロールバック手順: Phase 6 の committed_state 主要項目版へ戻す。

## 7. テスト計画
- 単体:
  - `ChatReply.mechanism.committed_state` が CCS 全量を含むこと。
  - in-memory 圧縮の既定語彙が日本語化されること。
- 結合:
  - `POST /api/chat/messages` に CCS 全項目が含まれること。
- 手動:
  - UI で送信後、CCS 全フィールドが見えることを確認。
- LLM/外部依存:
  - CI は in-memory アダプタのみ使用。
- 合格条件:
  - `uv run ruff format --check src tests`
  - `uv run ruff check src tests`
  - `uv run mypy src tests`
  - `uv run pytest -q`

## 8. 受け入れ基準
- UI 上で CCS 全9フィールドを確認できる。
- API レスポンスの `mechanism.committed_state` に CCS 全量が入っている。
- CCS 管理言語方針が日本語に統一され、英語の既定語彙が残らない。
- 既存チャット機能が維持される。

## 9. リスク / 対策
- リスク: 表示情報増加で UI が読みにくくなる。
- 対策: レイアウト調整と短縮整形を行う。
- リスク: OpenAI 出力の完全日本語保証は困難。
- 対策: プロンプトで強制し、必要なら将来バリデーションで英語比率チェックを追加。

## 10. オープン事項 / 要確認
- なし。

## 11. 実装タスクリスト
- [x] CCS 全量を `ChatReply`/API schema へ反映
- [x] `app.py` の response mapping 更新
- [x] UI に CCS 全項目表示を追加
- [x] OpenAI/in-memory の CCS 言語方針を日本語化
- [x] 単体/結合テスト更新
- [x] API ドキュメント更新
- [x] 品質コマンド実行

## 12. ドキュメント更新
- [ ] `README.md`（必要に応じて）
- [ ] `AGENTS.md`（必要に応じて）
- [x] `docs/task-designs/20260208203214_ccs-full-visualization-and-japanese-phase7.md`
- [x] `docs/api/chat-messages-post.md`
- [x] `docs/api/index.md`

## 13. 承認ログ
- 承認者: shogohasegawa
- 承認日時: 2026-02-08 20:33
- 承認コメント: OK

## 実装開始条件
- [x] ステータスが `承認済み(approved)` である
- [x] 10. オープン事項が空である
- [x] 受け入れ基準とテスト計画に合意済み
