# Agent Cognitive Compressor

ACC（Agent Cognitive Compressor）の実装リポジトリです。  
現在は OpenAI `gpt-4.1-mini` を使ったチャット API と簡易 HTML UI まで動作します。

## 1. ACCとは

ACC は、長いマルチターン対話で起きやすい「文脈肥大化」「制約の取りこぼし」「古い推測の引きずり」を抑えるための
**メモリ制御メカニズム**です。

一般的な「過去ログをそのまま積み上げる」方式ではなく、各ターンで意思決定に必要な状態だけを
`CCS (Compressed Cognitive State)` として圧縮・更新し続けます。  
この実装では、ACC の状態更新を API と UI で確認できるようにしています。

## 2. ACCの仕組み（1ターン）

1ターンごとに、ACC はおおむね次の流れで動きます。

1. `Recall`  
   現在入力と前ターンの CCS を使って、候補 Artifact（外部証拠）を想起します。
2. `Qualification`  
   想起した候補のうち、今回の意思決定に必要なものだけを通します。
3. `Commit`  
   通過した証拠を使って、次の CCS をスキーマ準拠でコミットします（前状態を置換）。
4. `Decide`  
   コミット済み CCS を条件に応答を生成し、ターン証拠を保存します。

ポイントは、**内部で持ち続ける状態を有界に保つ**ことです。  
外部の証拠ストアは増えても、内部の意思決定状態（CCS）は固定スキーマ内で管理されます。

## 3. 主要用語

- `CCS (Compressed Cognitive State)`: 各ターンで置換コミットされる内部状態。
- `Artifact`: 想起・評価対象になる外部証拠（過去ターン情報など）。
- `Schema-governed commitment`: CCS を定義済みスキーマに沿って検証・更新する方式。

## 4. CCS の構成項目

この実装で CCS は次の 9 項目で構成されます（`src/acc/domain/value_objects/ccs.py`）。

| 項目 | 意味 |
| --- | --- |
| `episodic_trace` | 直近ターンの出来事ログ（短いエピソード列）。 |
| `semantic_gist` | 現在対話の要点を圧縮した要約。 |
| `focal_entities` | いま注目すべき主体・対象（人名、システム名など）。 |
| `relational_map` | 事実や対象間の関係を表す情報。 |
| `goal_orientation` | この対話で追う目的・方針。 |
| `constraints` | 守るべき制約条件。 |
| `predictive_cue` | 次に取るべき行動や確認ポイントの手がかり。 |
| `uncertainty_signal` | 現在の不確実性レベル。 |
| `retrieved_artifacts` | 参照した Artifact のID一覧。 |

## 5. できること

- ACC のコアループ（想起 → 資格判定 → CCSコミット → 応答）を実行
- OpenAI Responses API 経由で `gpt-4.1-mini` に接続
- セッション単位のチャット API
- ブラウザで対話できる簡易 UI（`/`）
- メモリ評価指標（hallucination / drift / memory）の集計ロジック

## 6. セットアップ

```bash
uv sync --dev
```

環境変数は `.env.example` を参考に設定してください。最低限:

- `OPENAI_API_KEY`（必須）
- `OPENAI_MODEL`（任意、デフォルト: `gpt-4.1-mini`）

## 7. ローカル起動

```bash
uv run uvicorn acc.adapters.inbound.http.app:create_app --factory --reload
```

起動後:

- UI: `http://127.0.0.1:8000/`
- Health: `http://127.0.0.1:8000/api/health`

## 8. API 一覧

- `docs/api/index.md` を参照してください。

## 9. テスト

```bash
uv run ruff format --check src tests
uv run ruff check src tests
uv run mypy src tests
uv run pytest -q
```

## 10. 詳細ドキュメント

- ACC ブループリント（背景・設計・評価）: `docs/blue-print/arxiv-2601.11653.md`
- Hexagonal 構成: `docs/architecture/hexagonal-architecture.md`
- API仕様: `docs/api/`

## 11. ドキュメント運用

- エージェント向けルール: `AGENTS.md`
- タスク設計: `docs/task-designs/`
- API仕様: `docs/api/`
