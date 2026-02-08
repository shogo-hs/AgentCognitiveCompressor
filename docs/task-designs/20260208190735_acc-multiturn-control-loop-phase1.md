# タスク設計書: ACC マルチターン制御ループ Phase 1 実装

最終更新: 2026-02-08
- ステータス: 完了(done)
- 作成者: Codex
- レビュー: shogohasegawa
- 対象コンポーネント: backend / docs
- 関連: `docs/blue-print/arxiv-2601.11653.md`, `docs/architecture/hexagonal-architecture.md`
- チケット/リンク: 該当なし

## 0. TL;DR
- ブループリント 3.2/3.3 の中核である CCS スキーマと ACC 1ターン更新ループを、まずローカル実装可能な最小形で追加する。
- Hexagonal 構成に沿って `domain` に CCS/Artifact モデル、`ports` に圧縮・想起・判定・保存・意思決定の契約、`application` に制御ユースケースを配置する。
- 外部 LLM 依存は Phase 1 では導入せず、テスト可能なインメモリアダプタでアルゴリズム整合性を担保する。
- 単体テストで「有界想起」「資格判定」「状態置換」「証拠永続化」を検証し、以後の実運用アダプタ実装の土台にする。

## 1. 背景 / 課題
- 現状の実装は `health_check` のみで、`docs/blue-print/arxiv-2601.11653.md` が定義する ACC の記憶制御ループ（Algorithm 1）をコード上で追跡できない。
- 先に制御ループの契約を固めないと、後続の LLM 圧縮器・検索器・評価基盤を追加した際に責務が混在しやすい。
- そのため、ブループリントの概念を最小限の実装単位へ分解し、型で守られるコアを先に確立する必要がある。

## 2. ゴール / 非ゴール
### 2.1 ゴール
- CCS（Compressed Cognitive State）を型付きモデルとして定義する。
- ACC の 1 ターン更新ループ（想起→資格判定→圧縮コミット→エージェント実行→証拠保存）をユースケース化する。
- 外部依存なしでループを実行できるインメモリアダプタと単体テストを追加する。
- 既存 `health_check` テストを維持しつつ、新規テストで ACC コア挙動を回帰確認できる状態にする。

### 2.2 非ゴール
- 本番向け LLM（CCM）接続やベクトル DB 接続。
- 論文 5 章の judge 駆動評価（hallucination/drift 指標）のフル実装。
- API サーバー・CLI などの入出力インターフェース実装。

## 3. スコープ / 影響範囲
- 変更対象: `src/acc/domain/**`, `src/acc/ports/**`, `src/acc/application/**`, `src/acc/adapters/**`, `tests/unit/**`。
- 影響範囲: Python パッケージ内部の設計骨格と単体テスト。
- 互換性: 既存公開 API が無いため破壊的変更リスクは低い。`health_check` は維持。
- 依存関係: 標準ライブラリ中心（外部依存は追加しない）。

## 4. 要件
### 4.1 機能要件
- CCS を構成する主要要素（episodic_trace, semantic_gist, focal_entities, relational_map, goal_orientation, constraints, predictive_cue, uncertainty_signal, retrieved_artifacts）を保持できる。
- Artifact 想起は件数上限を受け取り、有界件数で候補を返せる。
- 資格判定を通過した Artifact のみが圧縮器へ渡される。
- コミット後の CCS は前状態を完全置換する（追記ではなく置換）。
- 各ターンの入力/意思決定を証拠ストアに保存できる。

### 4.2 非機能要件 / 制約
- Python 3.12+ 型ヒント準拠、`mypy` と `ruff` を通過する。
- docstring は日本語で簡潔に記述する。
- Hexagonal の依存方向（domain <- application <- adapters）を崩さない。

## 5. 仕様 / 設計
### 5.1 全体方針
- ブループリント Algorithm 1 を `application/use_cases` に写像し、外部 I/O は全て `ports` 契約経由で注入する。
- `domain` は純粋な値オブジェクトとエンティティに限定し、外部技術依存を持たせない。
- `adapters/outbound` にテスト用インメモリ実装を置き、将来の LLM/DB 実装差し替えを容易にする。

### 5.2 変更点一覧
| 対象 | 変更内容 | 影響 | 備考 |
| --- | --- | --- | --- |
| `src/acc/domain/value_objects/ccs.py` | CCS と関連値オブジェクトを追加 | コア状態表現を追加 | 論文 3.2 対応 |
| `src/acc/domain/entities/artifact.py` | Artifact エンティティを追加 | 想起/保存対象の統一 | provenance を保持 |
| `src/acc/domain/entities/interaction.py` | ターン入力・意思決定エンティティを追加 | ループ入出力の型安全化 | 3.3 対応 |
| `src/acc/ports/outbound/*.py` | Recall / Qualification / Compression / Decision / EvidenceStore 契約を追加 | 依存の抽象化 | Hexagonal 準拠 |
| `src/acc/application/use_cases/acc_multiturn_control_loop.py` | 1ターン更新と複数ターン実行ユースケースを追加 | ACC 実装中核 | Algorithm 1 を写像 |
| `src/acc/adapters/outbound/in_memory_acc_components.py` | インメモリ実装を追加 | ローカル検証可能化 | Phase 1 用 |
| `tests/unit/test_acc_multiturn_control_loop.py` | ループ仕様テストを追加 | 回帰防止 | 状態置換/想起上限など |

### 5.3 詳細
#### API
- 該当なし。

#### UI
- 該当なし。

#### データモデル / 永続化
- CCS は dataclass ベースの不変値オブジェクトとして扱う。
- Artifact は `artifact_id`, `content`, `source`, `created_at` を持つ。
- EvidenceStore は Phase 1 ではインメモリリスト永続化（プロセス内）とする。

#### 設定 / 環境変数
- 該当なし。

### 5.4 代替案と不採用理由
- 代替案A: 先に LLM/VectorDB を接続して実装する。
  - 不採用理由: コア契約が未確定のまま外部依存を入れると、責務分離とテスト容易性が低下する。
- 代替案B: ports を作らず application で直接処理する。
  - 不採用理由: Hexagonal 方針に反し、後続の実装差し替えコストが高くなる。

## 6. 移行 / ロールアウト
- 既存機能が小さいため一括反映する。
- ロールバック条件: 既存 `health_check` が壊れる、または新規テストで設計意図と異なる振る舞いが検出される場合。
- ロールバック手順: 追加ファイルを個別に戻し、`pytest` が再びグリーンになることを確認する。

## 7. テスト計画
- 単体:
  - `tests/unit/test_acc_multiturn_control_loop.py` で以下を検証する。
  - 想起件数が上限を超えないこと。
  - 資格判定不合格の Artifact が圧縮器へ渡らないこと。
  - 各ターンで CCS が置換されること。
  - 入力と意思決定が EvidenceStore に保存されること。
- 結合: 該当なし（Phase 1）。
- 手動:
  - `uv run ruff check src tests`
  - `uv run mypy src tests`
  - `uv run pytest -q`
- LLM/外部依存: インメモリアダプタで代替し、外部接続は行わない。
- 合格条件: 既存テスト + 新規テストが全て成功し、品質コマンドが通ること。

## 8. 受け入れ基準
- ACC ループのコアユースケースが `src/acc/application/use_cases/acc_multiturn_control_loop.py` に存在する。
- CCS と Artifact の型定義が `domain` に追加されている。
- ports と in-memory adapters により、外部依存なしで複数ターン実行が可能である。
- 新規テストが追加され、`pytest` で成功する。

## 9. リスク / 対策
- リスク: Phase 1 で CCS スキーマを厳密にしすぎると、後続の本番要件で変更が増える。
- 対策: 必須項目に限定した最小スキーマで実装し、拡張点は ports と dataclass で吸収する。
- リスク: インメモリ実装の挙動が本番実装と乖離する。
- 対策: テスト対象を「アルゴリズム上の契約（入力/出力/順序）」に限定し、実装依存ロジックを避ける。

## 10. オープン事項 / 要確認
- なし。

## 11. 実装タスクリスト
- [x] domain の CCS/Artifact/Interaction モデルを追加
- [x] outbound ports を追加
- [x] ACC ループユースケースを実装
- [x] in-memory adapters を実装
- [x] 単体テストを追加し、品質コマンドを実行

## 12. ドキュメント更新
- [ ] `README.md`（必要に応じて）
- [ ] `AGENTS.md`（必要に応じて）
- [x] `docs/task-designs/20260208190735_acc-multiturn-control-loop-phase1.md`

## 13. 承認ログ
- 承認者: shogohasegawa
- 承認日時: 2026-02-08 19:12
- 承認コメント: OK

## 実装開始条件
- [x] ステータスが `承認済み(approved)` である
- [x] 10. オープン事項が空である
- [x] 受け入れ基準とテスト計画に合意済み
