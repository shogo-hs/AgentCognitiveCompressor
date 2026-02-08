# タスク設計書: CCS空goal耐性とHTTPエラー分類改善 Phase 8 実装

最終更新: 2026-02-08
- ステータス: レビュー待ち(review-ready)
- 作成者: Codex
- レビュー: shogohasegawa
- 対象コンポーネント: backend / docs
- 関連: `docs/task-designs/20260208203214_ccs-full-visualization-and-japanese-phase7.md`, `src/acc/domain/services/ccs_schema.py`, `src/acc/adapters/inbound/http/app.py`
- チケット/リンク: 該当なし

## 0. TL;DR
- 実行ログの `goal_orientation は空文字にできません。` は、LLM が空 `goal_orientation` を返したときの CCS 検証エラーに起因する。
- 現状 `app.py` が `ValueError` を一律 400 化するため、モデル由来エラーまで 400 で返ってしまう。
- `goal_orientation` のみ安全にフォールバックして処理継続し、残る CCS 検証エラーは 502 として返すよう修正する。
- 併せてテストを追加し、再発時の挙動を固定化する。

## 1. 背景 / 課題
- ユーザー実行時に `POST /api/chat/messages` が 400 を返し、詳細が `goal_orientation は空文字にできません。` となった。
- これはユーザー入力不正ではなく、OpenAI 圧縮出力の品質揺らぎに起因するため、UX とエラー分類が不適切。
- チャット体験としては、空 goal だけで失敗しない耐性と、失敗時の適切な 5xx 化が必要。

## 2. ゴール / 非ゴール
### 2.1 ゴール
- `goal_orientation` が空文字のとき、前ターンの goal または日本語既定 goal にフォールバックして継続する。
- フォールバック不能な CCS 検証エラーは `502 Bad Gateway` として返す。
- テストで上記挙動を担保する。

### 2.2 非ゴール
- CCS 全フィールドに対する包括的自動補正。
- OpenAI 応答の完全保証（モデル側揺らぎそのものの解消）。
- API エンドポイント追加。

## 3. スコープ / 影響範囲
- 変更対象:
  - `src/acc/adapters/outbound/schema_aware_cognitive_compressor.py`
  - `src/acc/adapters/inbound/http/app.py`
  - `src/acc/adapters/outbound/openai_chat_adapters.py`（指示文補強）
  - `tests/unit/test_schema_aware_cognitive_compressor.py`
  - `tests/unit/test_http_chat_api.py`
  - `docs/task-designs/20260208203927_ccs-empty-goal-robustness-phase8.md`
- 影響範囲: 異常系のレスポンスコード、CCS commit の耐障害性。
- 互換性: 正常系レスポンス構造は不変。
- 依存関係: 新規ライブラリ追加なし。

## 4. 要件
### 4.1 機能要件
- `SchemaAwareCognitiveCompressorAdapter` で以下を実施:
  - 初回検証失敗が `goal_orientation` 空文字の場合のみ payload 補正して再検証。
  - 補正値: `committed_state.goal_orientation` が空でなければそれ、空なら `タスク整合性を維持する`。
- `app.py` で `CCSValidationError` を `502` へマッピング。
- OpenAI 圧縮 instructions に「goal_orientation は空文字禁止、未確定時は既存goal維持」を追記。

### 4.2 非機能要件 / 制約
- 既存の 400（入力不正）と 404（session不在）挙動を維持。
- `ruff` / `mypy` / `pytest` を通す。

## 5. 仕様 / 設計
### 5.1 全体方針
- 検証ルール自体（`ccs_schema.py`）は厳格なまま維持し、adapter 層で実運用耐性を追加する。
- HTTP 層ではエラー原因を分類して 4xx/5xx を適切化する。

### 5.2 変更点一覧
| 対象 | 変更内容 | 影響 | 備考 |
| --- | --- | --- | --- |
| `src/acc/adapters/outbound/schema_aware_cognitive_compressor.py` | empty goal の補正リトライを追加 | CCS commit 安定化 | goal 専用補正 |
| `src/acc/adapters/inbound/http/app.py` | `CCSValidationError` を 502 へ追加 | エラー分類適正化 | `ValueError` より先に捕捉 |
| `src/acc/adapters/outbound/openai_chat_adapters.py` | goal 非空制約を補強 | モデル指示改善 | 予防策 |
| `tests/unit/test_schema_aware_cognitive_compressor.py` | empty goal 補正の単体テスト追加 | 回帰防止 | |
| `tests/unit/test_http_chat_api.py` | CCSValidationError の 502 化テスト追加 | 回帰防止 | |

### 5.3 詳細
#### API
- 既存 endpoint は不変。
- `POST /api/chat/messages` で CCSValidationError は 502 + detail を返す。

#### UI
- UI 変更なし（HTTP ステータス分類改善のみ）。

#### データモデル / 永続化
- 変更なし。

#### 設定 / 環境変数
- 変更なし。

### 5.4 代替案と不採用理由
- 代替案A: `ccs_schema.py` で `goal_orientation` を空許容にする。
  - 不採用理由: スキーマ厳格性が崩れ、他経路での品質低下を招く。
- 代替案B: 空goal時に常に 502 で失敗させる。
  - 不採用理由: 実用上の耐性が低く、ユーザー体験を悪化させる。

## 6. 移行 / ロールアウト
- 追加ロジックのみで段階移行不要。
- ロールバック条件: 予期せぬ fallback により goal が不適切に固定される場合。
- ロールバック手順: fallback ロジックを外し、502分類のみ維持する。

## 7. テスト計画
- 単体:
  - empty `goal_orientation` payload が既存/既定 goal へ補正される。
- 結合:
  - `CCSValidationError` 発生時に `/api/chat/messages` が 502 を返す。
- 手動:
  - `dotenvx run -f .env.development -- uv run uvicorn ...` で複数ターン実行し再現しないことを確認。
- LLM/外部依存:
  - CI は in-memory とダミーモデルで検証。
- 合格条件:
  - `uv run ruff format --check src tests`
  - `uv run ruff check src tests`
  - `uv run mypy src tests`
  - `uv run pytest -q`

## 8. 受け入れ基準
- 同様条件で `goal_orientation` 空が発生しても、可能な範囲でチャット継続できる。
- 補正不能な CCS 検証エラーは 502 になる。
- 既存正常系 API/テストが維持される。

## 9. リスク / 対策
- リスク: fallback で古い goal を引き継ぎすぎる。
- 対策: 補正対象を `goal_orientation` 空文字時のみに限定する。
- リスク: 502 detail が内部実装依存になる。
- 対策: メッセージは簡潔にし、運用ログで詳細を追える構成を維持。

## 10. オープン事項 / 要確認
- なし。

## 11. 実装タスクリスト
- [ ] empty goal fallback を compressor adapter に追加
- [ ] `CCSValidationError` の 502 マッピング追加
- [ ] OpenAI instructions に goal 非空制約追加
- [ ] 単体/結合テスト追加
- [ ] 品質コマンド実行

## 12. ドキュメント更新
- [ ] `README.md`（必要に応じて）
- [ ] `AGENTS.md`（必要に応じて）
- [ ] `docs/task-designs/20260208203927_ccs-empty-goal-robustness-phase8.md`

## 13. 承認ログ
- 承認者: <名前>
- 承認日時: <YYYY-MM-DD HH:mm>
- 承認コメント: <条件付き承認の場合は条件を明記>

## 実装開始条件
- [ ] ステータスが `承認済み(approved)` である
- [ ] 10. オープン事項が空である
- [ ] 受け入れ基準とテスト計画に合意済み
