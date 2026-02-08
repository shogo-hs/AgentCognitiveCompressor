# タスク設計書: ACC ライブ評価オーケストレーション Phase 4 実装

最終更新: 2026-02-08
- ステータス: 完了(done)
- 作成者: Codex
- レビュー: shogohasegawa
- 対象コンポーネント: backend / docs
- 関連: `docs/blue-print/arxiv-2601.11653.md`, `docs/task-designs/20260208192231_acc-memory-evaluation-phase3.md`
- チケット/リンク: 該当なし

## 0. TL;DR
- ブループリント 5.1 の「judge 駆動ライブ評価」をコードで回せるよう、複数エージェント実行のオーケストレーション層を追加する。
- Phase 3 で作成した指標計算（集計器）は再利用し、Phase 4 では turn データ生成パイプラインを実装する。
- `ports` で judge/agent ランナー契約を定義し、`application` で episode 実行ユースケースを実装する。
- テストではダミー judge と scripted agent を用いて、turnごとに `AgentTurnEvaluationRecord` が正しく構築・集計されることを検証する。

## 1. 背景 / 課題
- 現在は評価指標の計算ロジック（式）は存在するが、ライブ実行で turn レコードを生成する実行器がない。
- そのため、複数エージェント（baseline / retrieval / acc）を同一 turn で比較する運用が手動依存になっている。
- 5.1 の評価手順（同一クエリ→各エージェント応答→judge 評価）を再現可能なユースケースとして実装する必要がある。

## 2. ゴール / 非ゴール
### 2.1 ゴール
- 複数エージェントを同一 turn query 列で実行し、agentごとの turn 評価レコードを生成できる。
- judge が返す outcome/audit 結果を `AgentTurnEvaluationRecord` に正規化し、Phase 3 集計器へ接続できる。
- episode 実行結果として agent別 summary を返せる。

### 2.2 非ゴール
- judge そのものの知能実装（LLM 推論や canonical memory 生成アルゴリズム）。
- 本番の外部 API 接続。
- 可視化やレポートレンダリング。

## 3. スコープ / 影響範囲
- 変更対象: `src/acc/ports/outbound/**`, `src/acc/domain/value_objects/**`, `src/acc/application/use_cases/**`, `tests/unit/**`。
- 影響範囲: 評価実行フロー（既存 ACC 制御ループロジックへの影響はなし）。
- 互換性: 既存の評価集計 API は維持し、上位ユースケースを追加する。
- 依存関係: 標準ライブラリのみ。

## 4. 要件
### 4.1 機能要件
- エージェント実行契約:
  - 入力: turn query, turn id, canonical memory
  - 出力: agent response text, memory token size
- judge 評価契約:
  - 入力: turn query, canonical memory, agent responses
  - 出力: canonical memory 更新結果 + agent別 outcome/audit
- ユースケース:
  - 複数 turn を順に実行し、agent別に `AgentTurnEvaluationRecord` を蓄積
  - episode 完了後、agent別 summary を返却

### 4.2 非機能要件 / 制約
- turn 順序を保証する（`turn_id` は 1..T）。
- judge から未知エージェント名が返った場合はエラーとする。
- `ruff` / `mypy` / `pytest` を通過する。

## 5. 仕様 / 設計
### 5.1 全体方針
- プロトコル駆動で実装し、judge/agent 実体は差し替え可能にする。
- canonical memory は opaque な `Mapping[str, object]` として扱い、judge が更新責務を持つ。
- Phase 3 の `AgentJudgeEvaluationUseCase` を内部利用して summary を得る。

### 5.2 変更点一覧
| 対象 | 変更内容 | 影響 | 備考 |
| --- | --- | --- | --- |
| `src/acc/domain/value_objects/live_evaluation.py` | turn query / agent response / judge turn result の型を追加 | 実行データ構造を明確化 | 5.1 対応 |
| `src/acc/ports/outbound/live_evaluation_ports.py` | agent runner / judge evaluator 契約を追加 | 実装差し替え性向上 | Hexagonal 準拠 |
| `src/acc/application/use_cases/live_multi_agent_evaluation.py` | ライブ評価実行ユースケースを追加 | Phase4 中核 | 5.1 フロー実装 |
| `tests/unit/test_live_multi_agent_evaluation.py` | オーケストレーションの単体テストを追加 | 回帰防止 | scripted dummy で検証 |
| `docs/task-designs/20260208192722_acc-live-evaluation-orchestration-phase4.md` | 本設計書を追加 | 実装前ゲート | 規約準拠 |

### 5.3 詳細
#### API
- 該当なし。

#### UI
- 該当なし。

#### データモデル / 永続化
- 永続化は実施せず、メモリ上で episode 実行する。
- canonical memory は judge が返す `Mapping[str, object]` を次 turn に渡す。

#### 設定 / 環境変数
- 該当なし。

### 5.4 代替案と不採用理由
- 代替案A: judge と agent 実行を use case 内に直書きする。
  - 不採用理由: 本番接続・テスト差し替えが困難になり、Hexagonal 方針に反する。
- 代替案B: Phase 4 でも集計器のみ拡張し実行器を作らない。
  - 不採用理由: 5.1 のライブ比較フローを再現できない。

## 6. 移行 / ロールアウト
- 既存コードへの破壊的変更は行わず、新規モジュールとして追加する。
- ロールバック条件: 既存テスト失敗、またはライブ評価結果が turn 単位で破綻する場合。
- ロールバック手順: Phase 4 追加ファイルのみ差し戻し、既存テストグリーンへ復帰。

## 7. テスト計画
- 単体:
  - 2エージェント・複数turnの scripted 入力で、turn レコード件数が一致する。
  - judge 更新 canonical memory が次 turn に引き継がれる。
  - summary が agent ごとに算出される。
  - judge 返却名と agent 名が不一致なら例外となる。
- 結合: 既存 Phase3 集計ユースケースを内部利用して連結確認する。
- 手動:
  - `uv run ruff format --check src tests`
  - `uv run ruff check src tests`
  - `uv run mypy src tests`
  - `uv run pytest -q`
- LLM/外部依存: ダミー実装で代替。
- 合格条件: 全品質コマンド成功、追加テスト成功。

## 8. 受け入れ基準
- 複数エージェント turn 実行ユースケースが追加されている。
- judge 出力から `AgentTurnEvaluationRecord` を自動生成できる。
- episode 結果として agent別 summary を返せる。
- 既存テスト含め全テストが成功する。

## 9. リスク / 対策
- リスク: canonical memory の型が曖昧で利用側が破壊的更新する可能性。
- 対策: use case 内で毎ターン shallow copy して受け渡す。
- リスク: judge 応答の agent 名不一致で silently データ欠損する。
- 対策: 不一致時に即例外を送出する。

## 10. オープン事項 / 要確認
- なし。

## 11. 実装タスクリスト
- [x] live evaluation 用 value object を追加
- [x] agent/judge ポートを追加
- [x] ライブ評価ユースケースを追加
- [x] 単体テストを追加
- [x] 品質コマンドを実行して結果確認

## 12. ドキュメント更新
- [ ] `README.md`（必要に応じて）
- [ ] `AGENTS.md`（必要に応じて）
- [x] `docs/task-designs/20260208192722_acc-live-evaluation-orchestration-phase4.md`

## 13. 承認ログ
- 承認者: shogohasegawa
- 承認日時: 2026-02-08 19:28
- 承認コメント: OK

## 実装開始条件
- [x] ステータスが `承認済み(approved)` である
- [x] 10. オープン事項が空である
- [x] 受け入れ基準とテスト計画に合意済み
