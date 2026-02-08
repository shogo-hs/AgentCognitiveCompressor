# タスク設計書: CCS意味準拠フォールバック Phase 9 実装

最終更新: 2026-02-08
- ステータス: 完了(done)
- 作成者: Codex
- レビュー: shogohasegawa
- 対象コンポーネント: backend / docs
- 関連: `docs/task-designs/20260208203927_ccs-empty-goal-robustness-phase8.md`, `docs/task-designs/20260208203214_ccs-full-visualization-and-japanese-phase7.md`, `src/acc/domain/services/ccs_schema.py`
- チケット/リンク: 該当なし

## 0. TL;DR
- 空NGの CCS 項目（`semantic_gist` / `goal_orientation` / `uncertainty_signal`）に対し、固定文言ではなく ACC 文脈から合成するフォールバックを実装する。
- フォールバックは `interaction_signal`・前回 `committed_state`・`qualified_artifacts` を用いた意味準拠ルールで算出する。
- API 側は CCS 検証エラーを 400 ではなく 502 に分類し、ユーザー入力不正と切り分ける。
- OpenAI への圧縮指示を補強し、空文字の生成を抑止する。

## 1. 背景 / 課題
- 実行時に `goal_orientation は空文字にできません。` が発生し、`POST /api/chat/messages` が 400 を返した。
- これはユーザー入力不正ではなくモデル出力揺らぎであり、4xx 返却は責務分離として不適切。
- また、単純な「固定デフォルト」だけでは ACC の内部意味（ターン文脈・制約・証拠）を反映できない。

## 2. ゴール / 非ゴール
### 2.1 ゴール
- 空NG3項目について、次の意味準拠フォールバックを実装する。
  - `semantic_gist`: 現ターン入力・目的・制約・証拠を要約した日本語短文
  - `goal_orientation`: 現ターン goal 優先、次に前回 goal、最後に入力/制約から合成
  - `uncertainty_signal`: 証拠量と不確実表現から `高/中/低` を推定
- フォールバック不能な CCS 検証エラーは `502` として返す。
- 回帰防止テストを追加する。

### 2.2 非ゴール
- CCS 全項目の自動修復（今回は空NG3項目のみ）。
- LLM 出力揺らぎの完全排除。
- UI 表示仕様の変更。

## 3. スコープ / 影響範囲
- 変更対象:
  - `src/acc/adapters/outbound/schema_aware_cognitive_compressor.py`
  - `src/acc/adapters/inbound/http/app.py`
  - `src/acc/adapters/outbound/openai_chat_adapters.py`
  - `tests/unit/test_schema_aware_cognitive_compressor.py`
  - `tests/unit/test_http_chat_api.py`
  - `docs/task-designs/20260208204341_ccs-semantic-fallback-phase9.md`
- 影響範囲: ACC commit 異常系、HTTP ステータス分類、圧縮指示の安定性。
- 互換性: 成功レスポンス形は不変。異常時コードのみ適正化（400→502）。
- 依存関係: 追加ライブラリなし。

## 4. 要件
### 4.1 機能要件
- `SchemaAwareCognitiveCompressorAdapter` に `payload` 補正ステップを追加する。
- 補正ルール:
  - `semantic_gist` が空/欠落/非文字列なら、以下で再生成
    - `user_input` 要約（必須）
    - `active_goal` または前回 goal を付与（あれば）
    - `active_constraints` または前回 constraints を付与（あれば）
    - `qualified_artifacts` 先頭要旨を根拠として付与（あれば）
  - `goal_orientation` が空/欠落/非文字列なら、優先順位で補正
    1. `interaction_signal.active_goal`
    2. `committed_state.goal_orientation`
    3. `user_input` と制約から合成（例:「<要件>を満たし、制約を順守する」）
  - `uncertainty_signal` が空/欠落/非文字列なら、規則推定
    - 証拠なし、または入力に不確実語（`不明` `わから` `確認できない` `推測` 等）: `高`
    - 証拠強い（qualified>=2 かつ前回 relational_map あり）: `低`
    - それ以外で証拠が最低限ある（qualified>=1）: `中`
- `app.py` で `CCSValidationError` を `502` にマップする（`ValueError` より先に捕捉）。
- OpenAI 圧縮 instructions に「3項目は非空必須・未確定時は文脈から埋める」を追記する。

### 4.2 非機能要件 / 制約
- 既存の 400（リクエスト不正）と 404（session 不在）を維持する。
- `ruff` / `mypy` / `pytest` を通す。
- `.env*` は変更しない。

## 5. 仕様 / 設計
### 5.1 全体方針
- スキーマ検証 (`ccs_schema.py`) は厳格に維持し、補正は adapter 層で行う。
- 補正対象を空NG3項目に限定し、他の不正は明示的に失敗させる。
- 補正値は固定語で終わらせず、ターン文脈を反映する。

### 5.2 変更点一覧
| 対象 | 変更内容 | 影響 | 備考 |
| --- | --- | --- | --- |
| `src/acc/adapters/outbound/schema_aware_cognitive_compressor.py` | 意味準拠フォールバック補正を追加 | commit 安定化 | 空NG3項目限定 |
| `src/acc/adapters/inbound/http/app.py` | `CCSValidationError` を 502 化 | HTTP分類適正化 | 4xx/5xx 分離 |
| `src/acc/adapters/outbound/openai_chat_adapters.py` | 非空3項目の指示強化 | 予防策 | 出力品質向上 |
| `tests/unit/test_schema_aware_cognitive_compressor.py` | フォールバック規則テスト追加 | 回帰防止 | |
| `tests/unit/test_http_chat_api.py` | CCS検証失敗の 502 テスト追加 | 回帰防止 | |

### 5.3 詳細
#### API
- エンドポイント不変。
- `POST /api/chat/messages` でモデル由来の CCS 検証失敗は 502 返却。

#### UI
- 変更なし。

#### データモデル / 永続化
- 変更なし。

#### 設定 / 環境変数
- 変更なし。

### 5.4 代替案と不採用理由
- 代替案A: 固定値で3項目を埋める。
  - 不採用理由: 文脈反映がなく、ACC の制御意味が弱まる。
- 代替案B: スキーマ側で空許容にする。
  - 不採用理由: CCS 品質基準が崩れる。

## 6. 移行 / ロールアウト
- 追加ロジックのみで段階移行不要。
- ロールバック条件: フォールバックが不適切な goal を頻発させる場合。
- ロールバック手順: 補正ルールを縮小し、502分類だけ維持。

## 7. テスト計画
- 単体:
  - 空3項目 payload で補正後に検証通過する。
  - goal は active_goal/前回goal 優先で選ばれる。
  - uncertainty は証拠量規則に従う。
- 結合:
  - 補正不能な `CCSValidationError` で `/api/chat/messages` が 502 を返す。
- 手動:
  - 同様の会話で 400 再発がないことを確認。
- 合格条件:
  - `uv run ruff format --check src tests`
  - `uv run ruff check src tests`
  - `uv run mypy src tests`
  - `uv run pytest -q`

## 8. 受け入れ基準
- 空NG3項目のうち、空出力が来ても意味準拠で補完される。
- ユーザー入力由来でない失敗は 502 として返る。
- 既存正常系レスポンスと UI 挙動が維持される。

## 9. リスク / 対策
- リスク: 合成 gist が冗長化する。
- 対策: 文字数上限を設ける（短文要約）。
- リスク: uncertainty 推定が過敏になる。
- 対策: キーワード判定は保守的にし、証拠量規則と併用する。

## 10. オープン事項 / 要確認
- なし。

## 11. 実装タスクリスト
- [x] 意味準拠フォールバックを実装
- [x] 502 マッピングを実装
- [x] OpenAI 指示文を補強
- [x] 単体/結合テスト追加
- [x] 品質コマンド実行

## 12. ドキュメント更新
- [ ] `README.md`（必要に応じて）
- [ ] `AGENTS.md`（必要に応じて）
- [x] `docs/task-designs/20260208204341_ccs-semantic-fallback-phase9.md`

## 13. 承認ログ
- 承認者: shogohasegawa
- 承認日時: 2026-02-08 20:44
- 承認コメント: OK

## 実装開始条件
- [x] ステータスが `承認済み(approved)` である
- [x] 10. オープン事項が空である
- [x] 受け入れ基準とテスト計画に合意済み
