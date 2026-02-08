# POST /api/chat/messages — チャットメッセージ送信

一覧: [ACC Chat API エンドポイント一覧](./index.md)
最終更新: `2026-02-08`

## 1. 概要

- 目的: 指定セッションで 1 ターン分の ACC 対話を実行し、応答を返す。
- 利用者/権限: すべての利用者（認証不要）。
- 副作用: セッション内の CCS/Artifact メモリが更新される。

## 2. リクエスト

### 2.1 ヘッダー

| 項目 | 必須 | 値 | 説明 |
| --- | --- | --- | --- |
| Content-Type | Yes | application/json | JSON ボディ送信時に必須 |

### 2.2 パスパラメータ

なし。

### 2.3 クエリパラメータ

なし。

### 2.4 リクエストボディ

| field | type | required | 制約 | 説明 | 例 |
| --- | --- | --- | --- | --- | --- |
| session_id | string | Yes | 1文字以上 | セッション識別子 | `3e3f26cf-57f8-4f78-9b35-1f2b6154132f` |
| message | string | Yes | 1..10000文字 | ユーザー入力 | `Nginx 502 の緩和策を教えて` |

### 2.5 リクエスト例

```bash
curl -X POST 'http://127.0.0.1:8000/api/chat/messages' \
  -H 'Content-Type: application/json' \
  -d '{
    "session_id": "3e3f26cf-57f8-4f78-9b35-1f2b6154132f",
    "message": "Nginx 502 の緩和策を教えて"
  }'
```

## 3. レスポンス

### 3.1 成功レスポンス

| Status | 条件 | 説明 |
| --- | --- | --- |
| 200 | 正常終了 | モデル応答と turn 情報を返す |

### 3.2 レスポンスボディ

| field | type | nullable | 説明 | 例 |
| --- | --- | --- | --- | --- |
| session_id | string | No | セッション識別子 | `3e3f26cf-57f8-4f78-9b35-1f2b6154132f` |
| turn_id | integer | No | セッション内ターン番号 | `1` |
| reply | string | No | ACC 経由の応答テキスト | `まず upstream latency を確認してください` |
| memory_tokens | integer | No | CCS 推定メモリトークン数 | `82` |
| mechanism | object | No | ACC 1ターン処理の可視化情報 | `{"recalled_artifact_count":1,...}` |

### 3.2.1 `mechanism` オブジェクト

| field | type | nullable | 説明 | 例 |
| --- | --- | --- | --- | --- |
| recalled_artifact_count | integer | No | Recall で想起した候補 Artifact 件数 | `2` |
| qualified_artifact_count | integer | No | Qualification で採用した Artifact 件数 | `1` |
| committed_state | object | No | Commit 後 CCS の主要項目 | `{"semantic_gist":"...","goal_orientation":"..."}` |

### 3.2.2 `mechanism.committed_state` オブジェクト

| field | type | nullable | 説明 | 例 |
| --- | --- | --- | --- | --- |
| semantic_gist | string | No | 現在ターンの要点要約 | `Nginx 502 を抑制しつつ原因確認` |
| goal_orientation | string | No | 継続中のゴール | `reduce_502_without_restart` |
| constraints | array[string] | No | 制約一覧 | `["no_restart","safe_change_only"]` |
| predictive_cue | array[string] | No | 次ターンで重視すべき観点 | `["check_upstream_latency"]` |
| uncertainty_signal | string | No | 不確実性シグナル | `medium` |
| retrieved_artifacts | array[string] | No | CCS に取り込んだ Artifact 参照 | `["turn-evidence-1-1"]` |

### 3.3 成功レスポンス例

```json
{
  "session_id": "3e3f26cf-57f8-4f78-9b35-1f2b6154132f",
  "turn_id": 1,
  "reply": "まず upstream latency を確認し、no_restart 制約下で timeout を調整します。",
  "memory_tokens": 82,
  "mechanism": {
    "recalled_artifact_count": 1,
    "qualified_artifact_count": 1,
    "committed_state": {
      "semantic_gist": "Nginx 502 の緩和策を確認する",
      "goal_orientation": "maintain-task-consistency",
      "constraints": [],
      "predictive_cue": [
        "next:assess-and-respond"
      ],
      "uncertainty_signal": "medium",
      "retrieved_artifacts": []
    }
  }
}
```

## 4. エラー

| Status | type | message例 | 発生条件 | クライアント対応 |
| --- | --- | --- | --- | --- |
| 400 | http_error | message は空にできません。 | ボディ不正 | 入力修正 |
| 404 | http_error | session_id が存在しません: missing-session | 不正セッションID | セッション再作成 |
| 502 | http_error | CCS payload JSON のパースに失敗しました。 | モデル返却フォーマット不正 | 再送または運用確認 |
| 503 | http_error | OpenAI 認証に失敗しました。OPENAI_API_KEY を確認してください。 | APIキー未設定/不正 | 環境変数設定 |

## 5. 備考

- モデルは既定で `gpt-4.1-mini` を利用する。
- `OPENAI_MODEL` 環境変数でモデル名を上書きできる。

## 6. 実装同期メモ

- 関連実装ファイル:
  - `src/acc/adapters/inbound/http/app.py`
  - `src/acc/application/use_cases/chat_session.py`
  - `src/acc/adapters/outbound/openai_chat_adapters.py`
- 関連テスト: `tests/unit/test_http_chat_api.py`, `tests/unit/test_chat_session.py`
- 未解決事項: なし
