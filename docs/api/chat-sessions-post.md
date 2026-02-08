# POST /api/chat/sessions — チャットセッション作成

一覧: [ACC Chat API エンドポイント一覧](./index.md)
最終更新: `2026-02-08`

## 1. 概要

- 目的: 新しいチャットセッションを作成し `session_id` を返す。
- 利用者/権限: すべての利用者（認証不要）。
- 副作用: サーバープロセス内メモリにセッション状態を作成する。

## 2. リクエスト

### 2.1 ヘッダー

| 項目 | 必須 | 値 | 説明 |
| --- | --- | --- | --- |
| Content-Type | No | application/json | ボディなしのため不要 |

### 2.2 パスパラメータ

なし。

### 2.3 クエリパラメータ

なし。

### 2.4 リクエストボディ

なし。

### 2.5 リクエスト例

```bash
curl -X POST 'http://127.0.0.1:8000/api/chat/sessions'
```

## 3. レスポンス

### 3.1 成功レスポンス

| Status | 条件 | 説明 |
| --- | --- | --- |
| 200 | 正常終了 | 新規 `session_id` を返す |

### 3.2 レスポンスボディ

| field | type | nullable | 説明 | 例 |
| --- | --- | --- | --- | --- |
| session_id | string | No | セッション識別子(UUID) | `3e3f26cf-57f8-4f78-9b35-1f2b6154132f` |

### 3.3 成功レスポンス例

```json
{
  "session_id": "3e3f26cf-57f8-4f78-9b35-1f2b6154132f"
}
```

## 4. エラー

定義済みエラーなし（入力なし・認証なし）。

## 5. 備考

- セッションは in-memory 管理のため、サーバー再起動で消える。

## 6. 実装同期メモ

- 関連実装ファイル: `src/acc/adapters/inbound/http/app.py`, `src/acc/application/use_cases/chat_session.py`
- 関連テスト: `tests/unit/test_http_chat_api.py`, `tests/unit/test_chat_session.py`
- 未解決事項: なし
