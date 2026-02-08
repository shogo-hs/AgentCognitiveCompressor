# タスク設計書: ACC メモリ評価基盤 Phase 3 実装

最終更新: 2026-02-08
- ステータス: 完了(done)
- 作成者: Codex
- レビュー: shogohasegawa
- 対象コンポーネント: backend / docs
- 関連: `docs/blue-print/arxiv-2601.11653.md`, `docs/task-designs/20260208190735_acc-multiturn-control-loop-phase1.md`, `docs/task-designs/20260208191756_acc-schema-governed-commitment-phase2.md`
- チケット/リンク: 該当なし

## 0. TL;DR
- ブループリント 5.2/5.3/5.4 に対応するため、ACC の評価指標計算基盤を追加する。
- turn-level の outcome / hallucination / drift / memory footprint を型で表現し、論文記載の式どおりに集計する。
- application ユースケースとして「単一エージェント集計」と「複数エージェント比較集計」を実装する。
- 単体テストで式の正しさ（`H_t`, `H_u`, `D_t`, `D_r`, `M̄`, `M_T`）を固定値で検証する。

## 1. 背景 / 課題
- 現状は ACC の制御ループ（3章）とスキーマ準拠コミット（Phase 2）まで実装済みで、5章の評価定義がコードに未反映。
- 評価ロジックがないため、長期ターンでの hallucination/drift/memory の改善を再現可能に比較できない。
- まず deterministic な指標計算基盤を追加し、将来の judge 実装や実データ投入の受け皿を整える必要がある。

## 2. ゴール / 非ゴール
### 2.1 ゴール
- turn-level 評価データの型（outcome・監査・memory）を追加する。
- 以下の式を実装し、ユースケース経由で summary を返せるようにする。
  - `H_t = U_t / max(1, S_t + U_t)`
  - `H_u = mean(H_t)`
  - `D_t = (V_t + O_t) / max(1, |K_t|)`
  - `D_r = mean(D_t for t>=2)`
  - `M̄ = mean(M_t)`, `M_T = 最終ターンメモリ`
- 複数エージェント（baseline/retrieval/acc）の比較集計を可能にする。

### 2.2 非ゴール
- LLM judge の推論実装（claim 抽出や支持判定）。
- 可視化（グラフ出力）実装。
- API/CLI の公開インターフェース実装。

## 3. スコープ / 影響範囲
- 変更対象: `src/acc/domain/value_objects/**`, `src/acc/domain/services/**`, `src/acc/application/use_cases/**`, `tests/unit/**`。
- 影響範囲: 評価集計ロジック（既存 ACC ループには非破壊）。
- 互換性: 既存機能は維持し、評価モジュールを追加する。
- 依存関係: 標準ライブラリのみ（新規依存なし）。

## 4. 要件
### 4.1 機能要件
- outcome 指標（relevance / answer_quality / instruction_following / coherence）を 0-10 前提で保持できる。
- hallucination 監査（supported/unsupported）から turn-level rate を計算できる。
- drift 監査（violations/omissions/active_constraints）から turn-level rate を計算できる。
- turn レコード列から agent summary を算出できる（平均・標準偏差・系列）。
- エージェント名→turnレコード列の辞書を受け取り、比較サマリー辞書を返せる。

### 4.2 非機能要件 / 制約
- 0除算は `max(1, ...)` で回避し、論文定義に合わせる。
- drift の平均は turn1 除外（drift監査が未定義の想定）に対応する。
- 型ヒントを必須とし `mypy` を通過する。

## 5. 仕様 / 設計
### 5.1 全体方針
- 数式ロジックは `domain/services` で純粋関数として実装する。
- 集計オーケストレーションは `application/use_cases` に配置する。
- データ受け渡しは dataclass ベースの value object に統一する。

### 5.2 変更点一覧
| 対象 | 変更内容 | 影響 | 備考 |
| --- | --- | --- | --- |
| `src/acc/domain/value_objects/evaluation.py` | turnレコード/summary の型を追加 | 評価データの型安全化 | 5章データモデル |
| `src/acc/domain/services/evaluation_metrics.py` | 指標計算関数を追加 | 数式実装の中核 | `H_t`, `D_t`, `M̄` など |
| `src/acc/application/use_cases/agent_judge_evaluation.py` | 単一/複数エージェント集計ユースケースを追加 | 実行導線追加 | judge 実装の受け皿 |
| `tests/unit/test_agent_judge_evaluation.py` | 指標計算の単体テストを追加 | 回帰防止 | 固定値で式検証 |
| `docs/task-designs/20260208192231_acc-memory-evaluation-phase3.md` | 本設計書を追加 | 実装前ゲート | 規約準拠 |

### 5.3 詳細
#### API
- 該当なし。

#### UI
- 該当なし。

#### データモデル / 永続化
- `AgentTurnEvaluationRecord` に turn-level の監査カウントとメモリトークン数を保持。
- 永続化は行わず、インメモリ集計のみ行う。

#### 設定 / 環境変数
- 該当なし。

### 5.4 代替案と不採用理由
- 代替案A: いきなり LLM judge を実装する。
  - 不採用理由: まず deterministic な式計算を固定しないと、評価誤差の原因を分離できない。
- 代替案B: 集計ロジックをテスト側ユーティリティに置く。
  - 不採用理由: 本番コードから再利用できず、責務分離が崩れる。

## 6. 移行 / ロールアウト
- 既存実装を変更せず、評価モジュールを追加する。
- ロールバック条件: 既存テスト失敗や、計算結果が論文式と一致しない場合。
- ロールバック手順: 追加ファイルを差し戻し、既存テストグリーンを確認する。

## 7. テスト計画
- 単体:
  - 固定入力で `H_t`, `H_u`, `D_t`, `D_r` が期待値と一致する。
  - turn1 に drift データがなくても平均 drift が算出できる。
  - memory 平均と最終値が期待どおりになる。
  - 複数エージェント比較で各 summary が独立に計算される。
- 結合: 既存 ACC ループとの直接結合は行わず、集計モジュール単体を検証する。
- 手動:
  - `uv run ruff format --check src tests`
  - `uv run ruff check src tests`
  - `uv run mypy src tests`
  - `uv run pytest -q`
- LLM/外部依存: なし。
- 合格条件: 全品質コマンド成功、追加テスト成功。

## 8. 受け入れ基準
- 5章の主要指標式がコード化されている。
- 単一/複数エージェント向けの集計ユースケースが利用可能。
- 固定値テストで計算結果が再現可能である。
- 既存テスト含めすべて成功する。

## 9. リスク / 対策
- リスク: 浮動小数点比較の誤差でテストが不安定になる。
- 対策: `pytest.approx` を使用して許容誤差付きで検証する。
- リスク: turn1 drift 除外ルールの扱いが曖昧になる。
- 対策: `drift_audit` を optional にし、平均計算時の除外規則を明示実装する。

## 10. オープン事項 / 要確認
- なし。

## 11. 実装タスクリスト
- [x] 評価用 value object を追加
- [x] 指標計算 service を追加
- [x] 集計ユースケースを追加
- [x] 単体テストを追加
- [x] 品質コマンドを実行して結果確認

## 12. ドキュメント更新
- [ ] `README.md`（必要に応じて）
- [ ] `AGENTS.md`（必要に応じて）
- [x] `docs/task-designs/20260208192231_acc-memory-evaluation-phase3.md`

## 13. 承認ログ
- 承認者: shogohasegawa
- 承認日時: 2026-02-08 19:23
- 承認コメント: OK

## 実装開始条件
- [x] ステータスが `承認済み(approved)` である
- [x] 10. オープン事項が空である
- [x] 受け入れ基準とテスト計画に合意済み
