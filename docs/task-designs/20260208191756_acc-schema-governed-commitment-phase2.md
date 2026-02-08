# タスク設計書: ACC スキーマ準拠コミット Phase 2 実装

最終更新: 2026-02-08
- ステータス: 完了(done)
- 作成者: Codex
- レビュー: shogohasegawa
- 対象コンポーネント: backend / docs
- 関連: `docs/blue-print/arxiv-2601.11653.md`, `docs/task-designs/20260208190735_acc-multiturn-control-loop-phase1.md`
- チケット/リンク: 該当なし

## 0. TL;DR
- Phase 1 で実装した ACC ループに対し、論文 3.1/3.2 の「schema-governed commitment」をコードで明示する。
- `domain/services` に CCS スキーマ検証・正規化ロジックを追加し、CCM 出力を deterministic に parse/validate する。
- `ports` に CCM 呼び出し契約を追加し、`adapters` に schema-aware な圧縮アダプタ（モデル呼び出し + 検証）を実装する。
- テストで「正常系」「必須項目欠落」「型不整合」「件数上限正規化」を検証し、追加モデル呼び出しなしで整合性を保証する。

## 1. 背景 / 課題
- 現状の `SimpleCognitiveCompressorAdapter` はルールベース更新であり、CCS スキーマ準拠の parse/validate 契約が明文化されていない。
- ブループリント 3.2 では「CCM 出力はスキーマに適合し、追加モデル呼び出しなしで deterministic に検証する」ことが要件化されている。
- この契約が未実装のままだと、将来 LLM 連携時に malformed state が入り込み、長期安定性と監査可能性が落ちる。

## 2. ゴール / 非ゴール
### 2.1 ゴール
- CCS スキーマの required fields / type constraints をコードで定義する。
- 任意の CCM 出力 payload を `CompressedCognitiveState` へ安全に変換する validator/parser を実装する。
- モデル呼び出しを隠蔽する `CognitiveCompressorModelPort` を追加し、schema-aware compressor adapter を実装する。
- 単体テストで失敗ケースを含めたスキーマ準拠性を担保する。

### 2.2 非ゴール
- 外部 API（OpenAI 等）への実接続。
- Retrieval アダプタのベクトル DB 化。
- 5章の judge 評価フレームワーク実装。

## 3. スコープ / 影響範囲
- 変更対象: `src/acc/domain/services/**`, `src/acc/ports/outbound/**`, `src/acc/adapters/outbound/**`, `tests/unit/**`。
- 影響範囲: 認知圧縮コンポーネントの責務分離と検証ロジック。
- 互換性: 既存 `SimpleCognitiveCompressorAdapter` は維持し、追加実装として導入する。
- 依存関係: 標準ライブラリのみ（新規パッケージ追加なし）。

## 4. 要件
### 4.1 機能要件
- CCS スキーマ定義（9フィールド）を required として扱う。
- list/tuple フィールドは文字列配列として正規化し、件数上限を適用する。
- 文字列フィールドが空/欠落のときは検証エラーを返す。
- schema-aware compressor は以下を行う:
  - 1) interaction / prior CCS / qualified artifacts からモデル入力を構築
  - 2) モデルから payload を取得
  - 3) payload を deterministic に parse/validate
  - 4) `CompressedCognitiveState` を返す

### 4.2 非機能要件 / 制約
- Hexagonal の依存方向を維持する（domain が adapter に依存しない）。
- 例外メッセージはデバッグ可能な粒度で返す（不足キー名や型不一致フィールドを含む）。
- `ruff` / `mypy` / `pytest` を通過する。

## 5. 仕様 / 設計
### 5.1 全体方針
- スキーマ検証は `domain/services` に置き、純粋関数で再利用可能にする。
- モデル呼び出しは `ports/outbound` で抽象化し、adapter 側で依存注入する。
- 既存 loop 互換を保つため、`CognitiveCompressorPort` インターフェースは変更しない。

### 5.2 変更点一覧
| 対象 | 変更内容 | 影響 | 備考 |
| --- | --- | --- | --- |
| `src/acc/domain/services/ccs_schema.py` | CCS 検証/正規化ロジックと例外型を追加 | スキーマ準拠の中核 | 3.2 対応 |
| `src/acc/ports/outbound/cognitive_compressor_model_port.py` | CCM 呼び出し契約を追加 | モデル依存の抽象化 | Hexagonal 準拠 |
| `src/acc/adapters/outbound/schema_aware_cognitive_compressor.py` | モデル呼び出し + validate を行う圧縮アダプタを追加 | 実運用への橋渡し | Phase 2 中核 |
| `tests/unit/test_schema_aware_cognitive_compressor.py` | スキーマ検証の正常/異常テストを追加 | 回帰防止 | 欠落/型不一致を検証 |
| `docs/task-designs/20260208191756_acc-schema-governed-commitment-phase2.md` | 本設計書を追加 | 実装前ゲート | 規約準拠 |

### 5.3 詳細
#### API
- 該当なし。

#### UI
- 該当なし。

#### データモデル / 永続化
- `CCSPayload` は `dict[str, object]` として受け取り、`CompressedCognitiveState` へ変換する。
- 永続化方式の追加は行わない（既存 EvidenceStore を利用）。

#### 設定 / 環境変数
- 該当なし。

### 5.4 代替案と不採用理由
- 代替案A: `SimpleCognitiveCompressorAdapter` に検証ロジックを直書きする。
  - 不採用理由: スキーマ責務が adapter に混在し、再利用性・テスト容易性が落ちる。
- 代替案B: `jsonschema` 依存を追加する。
  - 不採用理由: 現時点では標準ライブラリのみで十分であり、依存追加コストに対する効果が小さい。

## 6. 移行 / ロールアウト
- 既存実装は残し、Phase 2 コンポーネントを追加する。
- ロールバック条件: 既存 ACC ループ利用コードに型不整合が生じる場合。
- ロールバック手順: Phase 2 追加ファイルのみ差し戻し、Phase 1 のテストグリーンへ復帰する。

## 7. テスト計画
- 単体:
  - 正常系: 妥当 payload が `CompressedCognitiveState` に変換される。
  - 異常系: required field 欠落で `CCSValidationError` が発生する。
  - 異常系: list/string の型不一致で `CCSValidationError` が発生する。
  - 正規化: 配列フィールドが上限件数で切り詰められる。
- 結合: 既存 `ACCMultiturnControlLoop` に schema-aware compressor を差し込んで1ターン実行できること。
- 手動:
  - `uv run ruff format --check src tests`
  - `uv run ruff check src tests`
  - `uv run mypy src tests`
  - `uv run pytest -q`
- LLM/外部依存: テスト用ダミーモデルで代替する。
- 合格条件: 上記コマンド成功、追加テストが全件成功。

## 8. 受け入れ基準
- CCS スキーマ検証が `domain/services` として独立している。
- schema-aware compressor adapter が `CognitiveCompressorModelPort` 経由で payload を取得・検証して CCS を返せる。
- 欠落キー/型不一致ケースがテストで検出できる。
- 既存テストを含め全テストが成功する。

## 9. リスク / 対策
- リスク: スキーマを厳密にしすぎて将来拡張がしづらくなる。
- 対策: 未知フィールドは無視し、required/type の最小契約に限定する。
- リスク: 例外設計が曖昧で運用時に原因追跡が困難。
- 対策: 例外にフィールド名と期待型を含める。

## 10. オープン事項 / 要確認
- なし。

## 11. 実装タスクリスト
- [x] CCS スキーマ検証ロジックを追加
- [x] CCM モデル呼び出しポートを追加
- [x] schema-aware compressor adapter を実装
- [x] 単体テストを追加
- [x] 品質コマンドを実行して結果確認

## 12. ドキュメント更新
- [ ] `README.md`（必要に応じて）
- [ ] `AGENTS.md`（必要に応じて）
- [x] `docs/task-designs/20260208191756_acc-schema-governed-commitment-phase2.md`

## 13. 承認ログ
- 承認者: shogohasegawa
- 承認日時: 2026-02-08 19:18
- 承認コメント: OK

## 実装開始条件
- [x] ステータスが `承認済み(approved)` である
- [x] 10. オープン事項が空である
- [x] 受け入れ基準とテスト計画に合意済み
