# タスク設計書: OpenAI対応チャットUI Phase 5 実装

最終更新: 2026-02-08
- ステータス: 完了(done)
- 作成者: Codex
- レビュー: shogohasegawa
- 対象コンポーネント: backend / docs / frontend
- 関連: `docs/blue-print/arxiv-2601.11653.md`, `docs/task-designs/20260208192722_acc-live-evaluation-orchestration-phase4.md`, `docs/api/index.md`
- チケット/リンク: 該当なし

## 0. TL;DR
- `gpt-4.1-mini` を利用する OpenAI アダプタを追加し、ACC ループを実際に対話で使える状態にする。
- FastAPI ベースの最小 HTTP サーバーを追加し、セッション付きチャット API と静的 HTML UI を提供する。
- API 実装に合わせて `docs/api/index.md` とエンドポイント詳細ドキュメントを同期更新する。
- API キーは利用者設定前提にし、リポジトリには秘密値を保存しない。

## 1. 背景 / 課題
- 現在は ACC コアと評価基盤はあるが、実運用で人が対話できる入出力インターフェースがない。
- ユーザー要望は「OpenAI `gpt-4.1-mini` で実際に利用可能にし、簡単な HTML チャットUIを用意する」こと。
- このため、LLM 実接続・セッション管理・HTTP API・UI を最小構成で統合する必要がある。

## 2. ゴール / 非ゴール
### 2.1 ゴール
- OpenAI API を使う `AgentPolicyPort` / `CognitiveCompressorModelPort` の実装を追加する。
- チャットセッションを in-memory で保持し、ACC 状態をターンごとに更新できる。
- 以下 API を提供する。
  - `POST /api/chat/sessions`（セッション作成）
  - `POST /api/chat/messages`（ユーザー発話→ACC応答）
  - `GET /api/health`（疎通確認）
- `/` で最小 HTML チャット UI を表示し、上記 API と連動できる。
- ローカル実行手順を README と API ドキュメントに反映する。

### 2.2 非ゴール
- DB 永続化（セッションはプロセス内メモリ保持のみ）。
- 認証付き本番運用（ローカル開発用途の簡易構成）。
- フロントエンド高度機能（履歴検索、リッチUI、デザインシステム）。

## 3. スコープ / 影響範囲
- 変更対象:
  - `src/acc/adapters/outbound/**`（OpenAI アダプタ）
  - `src/acc/adapters/inbound/**`（FastAPI + static配信）
  - `src/acc/application/**`（チャットセッションユースケース）
  - `src/acc/domain/**`（セッション関連 value object 必要分）
  - `docs/api/**`（api-spec-sync）
  - `README.md`, `.env.example`（実行導線）
  - `pyproject.toml`, `uv.lock`（依存追加）
- 影響範囲: ローカル起動フロー、API 仕様、UI 導線。
- 互換性: 既存テストを壊さず機能追加として提供。
- 依存関係: `fastapi`, `uvicorn`, `openai`（`uv add` で追加）。

## 4. 要件
### 4.1 機能要件
- OpenAI モデルは既定で `gpt-4.1-mini` を使用する。
- `OPENAI_API_KEY` 未設定時は API 呼び出し時に明確なエラーを返す。
- セッションごとに以下を保持する:
  - `CompressedCognitiveState`
  - Artifact memory
  - ターンカウント
- チャット応答は ACC ループを通して生成する（単純な直接応答にしない）。
- HTML UI は以下を備える:
  - セッション開始ボタン
  - メッセージ入力/送信
  - 応答表示
  - エラー表示

### 4.2 非機能要件 / 制約
- Python 依存追加は `uv add` を使用する（`pip install` 禁止）。
- 秘密情報はコード・ドキュメントに埋め込まない。
- `ruff` / `mypy` / `pytest` を通過する。

## 5. 仕様 / 設計
### 5.1 全体方針
- Hexagonal 方針に従い、HTTP と OpenAI は adapter 層に閉じ込める。
- チャット実行は application ユースケース化し、API 層は I/O 変換のみ担当する。
- API 仕様は `api-spec-sync` に従って実装同時更新する。

### 5.2 変更点一覧
| 対象 | 変更内容 | 影響 | 備考 |
| --- | --- | --- | --- |
| `src/acc/adapters/outbound/openai_chat_adapters.py` | OpenAI policy/compressor 実装を追加 | LLM 実接続 | `gpt-4.1-mini` 既定 |
| `src/acc/application/use_cases/chat_session.py` | セッション管理ユースケース追加 | 対話実行導線 | ACCループを内包 |
| `src/acc/adapters/inbound/http/app.py` | FastAPI アプリ追加 | HTTP提供 | API + static配信 |
| `src/acc/adapters/inbound/http/static/index.html` | 簡易チャットUI追加 | ブラウザ利用 | 最小UI |
| `src/acc/adapters/inbound/http/schemas.py` | リクエスト/レスポンス DTO 追加 | API整合 | 型安全 |
| `docs/api/index.md` | 共通仕様・一覧を実実装に更新 | 仕様同期 | api-spec-sync |
| `docs/api/chat-sessions-post.md` | セッション作成 API 詳細追加 | 仕様同期 | 新規 |
| `docs/api/chat-messages-post.md` | メッセージ送信 API 詳細追加 | 仕様同期 | 新規 |
| `docs/api/health-get.md` | health API 詳細追加 | 仕様同期 | 新規 |
| `README.md`, `.env.example` | 起動手順・設定項目更新 | 利用導線改善 | |
| `pyproject.toml`, `uv.lock` | runtime 依存追加 | 実行可能化 | `uv add` |
| `tests/unit/test_chat_session.py` | セッションロジック単体テスト追加 | 回帰防止 | OpenAI呼び出しはモック |
| `tests/unit/test_http_chat_api.py` | FastAPI API テスト追加 | 回帰防止 | TestClient 利用 |

### 5.3 詳細
#### API
- `POST /api/chat/sessions`
  - 入力: 任意（将来拡張用に空ボディ許可）
  - 出力: `session_id`
- `POST /api/chat/messages`
  - 入力: `session_id`, `message`
  - 出力: `session_id`, `reply`, `turn_id`
- `GET /api/health`
  - 出力: `{"status":"ok"}` 相当

#### UI
- シングル HTML + 素の JavaScript で実装する。
- `/api/chat/sessions` で session 作成後、`/api/chat/messages` を順次呼ぶ。

#### データモデル / 永続化
- セッション情報は in-memory dict（プロセス単位）。
- サーバー再起動で消える仕様（非ゴールに明示）。

#### 設定 / 環境変数
- `OPENAI_API_KEY`（必須）
- `OPENAI_MODEL`（任意、デフォルト `gpt-4.1-mini`）
- `ACC_SERVER_HOST`, `ACC_SERVER_PORT`（任意）

### 5.4 代替案と不採用理由
- 代替案A: バックエンドを作らず、フロントから OpenAI API を直接呼ぶ。
  - 不採用理由: APIキー露出リスクが高く、ACC ループ統合も困難。
- 代替案B: Streamlit で UI を作る。
  - 不採用理由: 依存が増え、Hexagonal の inbound adapter として API 再利用性が低い。

## 6. 移行 / ロールアウト
- 追加実装として反映し、既存ユースケースを破壊しない。
- ロールバック条件: 既存テスト失敗、または API 起動不可。
- ロールバック手順: 追加ファイルと依存変更を差し戻し、既存テストグリーンを確認する。

## 7. テスト計画
- 単体:
  - セッション作成、turn 増加、存在しない session_id のエラー。
  - OpenAI アダプタはモッククライアントで payload 構築を検証。
- 結合:
  - FastAPI TestClient で `health` / `sessions` / `messages` の正常系・異常系を検証。
- 手動:
  - `uv run ruff format --check src tests`
  - `uv run ruff check src tests`
  - `uv run mypy src tests`
  - `uv run pytest -q`
  - `uv run uvicorn acc.adapters.inbound.http.app:create_app --factory --reload`
  - ブラウザで `http://127.0.0.1:8000/` を開き対話確認
- LLM/外部依存:
  - CI では OpenAI 呼び出しを行わない（モック/スタブ）。
  - 手動確認時のみ実 API キーで疎通確認。
- 合格条件: すべての品質コマンド成功、ローカル UI で1往復以上の対話成功。

## 8. 受け入れ基準
- `gpt-4.1-mini` を使ったチャット応答がローカルで実行できる。
- HTML UI からセッション作成・送信・応答表示が可能。
- API ドキュメント (`docs/api/index.md` + 各 endpoint) が実装と一致。
- 既存 + 新規テストが成功する。

## 9. リスク / 対策
- リスク: OpenAI レスポンスの JSON 逸脱で CCS 変換が失敗する。
- 対策: schema-aware compressor を利用し、失敗時は明示的例外とする。
- リスク: in-memory セッション肥大化。
- 対策: セッション数上限と簡易クリーンアップフックを実装する。
- リスク: API キー未設定時の UX 悪化。
- 対策: UI と API の両方で明確なエラーメッセージを返す。

## 10. オープン事項 / 要確認
- なし。

## 11. 実装タスクリスト
- [x] OpenAI アダプタを追加
- [x] チャットセッションユースケースを追加
- [x] FastAPI + HTML UI を追加
- [x] API ドキュメントを同期更新
- [x] テスト追加と品質コマンド実行

## 12. ドキュメント更新
- [x] `README.md`（起動手順）
- [ ] `AGENTS.md`（必要に応じて）
- [x] `docs/task-designs/20260208193504_openai-chat-ui-phase5.md`
- [x] `docs/api/index.md`
- [x] `docs/api/*.md`（endpoint 詳細）

## 13. 承認ログ
- 承認者: shogohasegawa
- 承認日時: 2026-02-08 19:36
- 承認コメント: OK

## 実装開始条件
- [x] ステータスが `承認済み(approved)` である
- [x] 10. オープン事項が空である
- [x] 受け入れ基準とテスト計画に合意済み
