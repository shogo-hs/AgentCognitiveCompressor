# ACC Chat API エンドポイント一覧

最終更新: `2026-02-08`
ベースURL: `http://127.0.0.1:8000`

## 1. 運用ルール

- API 実装の変更と同時にこの一覧を更新する。
- 1エンドポイントにつき詳細ドキュメントは1ファイルにする。
- 一覧リンク切れを残さない。

## 2. 共通仕様

### 2.1 認証

- 対象: なし（ローカル開発用）
- ヘッダー: 不要
- 未認証時: 該当なし

### 2.2 共通ヘッダー

- `Content-Type: application/json`（ボディありの場合）

### 2.3 エラーフォーマット

FastAPI の `HTTPException` による標準形式を返す。

```json
{
  "detail": "session_id が存在しません: missing-session"
}
```

### 2.4 タイムアウト・リトライ方針

- タイムアウト: クライアント側で制御
- リトライ: `POST /api/chat/messages` は非冪等のため自動リトライ非推奨

## 3. エンドポイント一覧

### System

- [GET /api/health](./health-get.md) - API 稼働確認

### Chat

- [POST /api/chat/sessions](./chat-sessions-post.md) - 新規チャットセッション作成
- [POST /api/chat/messages](./chat-messages-post.md) - セッション内で 1 ターン対話実行

## 4. 非推奨 / 廃止

- 該当なし

## 5. 変更履歴

- `2026-02-08`: 初版（Phase 5: OpenAI チャット API）
