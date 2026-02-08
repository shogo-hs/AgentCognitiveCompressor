# Agent Cognitive Compressor

ACC（Agent Cognitive Compressor）の実装リポジトリです。  
現在は OpenAI `gpt-4.1-mini` を使ったチャット API と簡易 HTML UI まで動作します。

## 1. できること

- ACC のコアループ（想起 → 資格判定 → CCSコミット → 応答）を実行
- OpenAI Responses API 経由で `gpt-4.1-mini` に接続
- セッション単位のチャット API
- ブラウザで対話できる簡易 UI（`/`）
- メモリ評価指標（hallucination / drift / memory）の集計ロジック

## 2. セットアップ

```bash
uv sync --dev
```

環境変数は `.env.example` を参考に設定してください。最低限:

- `OPENAI_API_KEY`（必須）
- `OPENAI_MODEL`（任意、デフォルト: `gpt-4.1-mini`）

## 3. ローカル起動

```bash
uv run uvicorn acc.adapters.inbound.http.app:create_app --factory --reload
```

起動後:

- UI: `http://127.0.0.1:8000/`
- Health: `http://127.0.0.1:8000/api/health`

## 4. API 一覧

- `docs/api/index.md` を参照してください。

## 5. テスト

```bash
uv run ruff format --check src tests
uv run ruff check src tests
uv run mypy src tests
uv run pytest -q
```

## 6. ドキュメント運用

- エージェント向けルール: `AGENTS.md`
- タスク設計: `docs/task-designs/`
- API仕様: `docs/api/`
