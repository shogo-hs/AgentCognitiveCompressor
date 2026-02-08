# タスク設計書: 短期対話バッファの環境変数化 Phase 11 実装

最終更新: 2026-02-08
- ステータス: 完了(done)
- 作成者: Codex
- レビュー: shogohasegawa
- 対象コンポーネント: backend / docs
- 関連: `docs/task-designs/20260208210520_acc-conversation-quality-alignment-phase10.md`, `docs/blue-print/arxiv-2601.11653.md`, `src/acc/application/use_cases/chat_session.py`
- チケット/リンク: 該当なし

## 0. TL;DR
- 相対参照質問（「一個前/二個前の発言」）の整合性を改善するため、短期対話バッファを追加する。
- バッファ長は環境変数で変更可能にし、デフォルトは **2ターン（2往復=最大4発話）** とする。
- CCS は引き続き唯一の永続内部状態とし、短期バッファはセッション内の一時情報として扱う。
- API契約は維持し、内部実装とテスト・READMEのみ更新する。

## 1. 背景 / 課題
- 現行実装は ACC コンセプトに沿って履歴再生をしないため、逐語的な直近参照質問に弱い。
- ユーザー要望として、短期履歴は持ちつつもコンセプトを崩さず、かつ設定可能にしたい。
- 固定値実装では運用時調整がしにくいため、環境変数で管理したい。

## 2. ゴール / 非ゴール
### 2.1 ゴール
- 直近2ターンをデフォルトで保持する短期対話バッファを導入する。
- バッファ長を環境変数で上書き可能にする。
- バッファ内容を AgentPolicy の入力にのみ渡し、相対参照質問への回答精度を改善する。
- CCS の構造・Commit フロー・置換セマンティクスを維持する。

### 2.2 非ゴール
- CCS スキーマ変更。
- Transcript replay（全履歴再投入）方式への回帰。
- 永続ストレージ（DB）への対話履歴保存。

## 3. スコープ / 影響範囲
- 変更対象: `ChatSessionUseCase` 内部状態、`AgentPolicyPort` 入力、OpenAI/in-memory policy adapter、`app.py` 設定解決、関連テスト、README。
- 影響範囲: 応答品質（相対参照の一貫性）、設定運用。
- 互換性: HTTP API 入出力は不変。内部ポート契約は拡張。
- 依存関係: 新規ライブラリ追加なし。

## 4. 要件
### 4.1 機能要件
- 環境変数 `ACC_SHORT_HISTORY_TURNS` を追加する（整数）。
- 既定値は `2` とする。
- `ChatSessionUseCase` で「ユーザー発話とアシスタント応答」のペアを最大 `N` ターン分リング保持する。
- `AgentPolicyPort.decide` へ短期バッファを引き渡せるようにする。
- OpenAI Policy prompt に短期バッファを含め、相対参照質問時は短期バッファ優先で回答する指示を与える。

### 4.2 非機能要件 / 制約
- ACC コンセプト維持:
  - 永続内部状態は CCS のみ。
  - 短期バッファはセッション内一時情報であり、CCS/Artifact永続化へは直接書き込まない。
- `ruff` / `mypy` / `pytest` を通す。

## 5. 仕様 / 設計
### 5.1 全体方針
- ブループリントの「CCSが唯一の永続内部状態」を守るため、短期バッファは **policy conditioning 専用の補助コンテキスト** とする。
- ACC の Recall/Qualify/Commit 経路は変更せず、Action（decide）入力のみ拡張する。

### 5.2 変更点一覧
| 対象 | 変更内容 | 影響 | 備考 |
| --- | --- | --- | --- |
| `src/acc/application/use_cases/chat_session.py` | セッション内短期対話バッファを追加、max turns管理 | 応答整合性向上 | 非永続 |
| `src/acc/ports/outbound/agent_policy_port.py` | `decide` に短期バッファ引数を追加 | 内部契約変更 | 全実装追従 |
| `src/acc/application/use_cases/acc_multiturn_control_loop.py` | `decide` 呼び出しへ短期バッファを渡す | 入力拡張 | |
| `src/acc/adapters/outbound/openai_chat_adapters.py` | prompt に短期バッファを追加 | 応答品質改善 | |
| `src/acc/adapters/outbound/in_memory_acc_components.py` | `EchoAgentPolicyAdapter` 追従 | テスト整合 | |
| `src/acc/adapters/inbound/http/app.py` | `ACC_SHORT_HISTORY_TURNS` 解決と use_case注入 | 設定運用性 | |
| `tests/unit/*.py` | 契約更新 + バッファ長挙動テスト追加 | 回帰防止 | |
| `README.md` | 新規環境変数説明追記 | ドキュメント整合 | |

### 5.3 詳細
#### API
- 変更なし。

#### UI
- 変更なし。

#### データモデル / 永続化
- CCS・Artifact のモデル変更なし。
- 短期バッファは `_SessionContext` のみ保持し、セッション破棄時に消える。

#### 設定 / 環境変数
- `ACC_SHORT_HISTORY_TURNS`（任意）
  - 未設定時: `2`
  - 0以上の整数を許容（`0` で短期バッファ無効化）
  - 不正値は `2` にフォールバック

### 5.4 代替案と不採用理由
- 代替案A: CCS に直近発話を埋め込む。
  - 不採用理由: CCS の責務肥大化とスキーマ汚染を招く。
- 代替案B: 全履歴を Artifact から毎回再構築して prompt 投入する。
  - 不採用理由: ACC の bounded memory 原則に反する。

## 6. 移行 / ロールアウト
- 段階移行不要。
- ロールバック条件: 応答品質悪化、または短期バッファによる不要な復唱増加。
- ロールバック手順: `ACC_SHORT_HISTORY_TURNS=0` で即時無効化し、必要に応じてコード差分を戻す。

## 7. テスト計画
- 単体:
  - 短期バッファが最大Nターンで切り詰められること。
  - `ACC_SHORT_HISTORY_TURNS` のデフォルト・上書き・不正値フォールバック。
- 結合:
  - 既存 `/api/chat/messages` フローが壊れないこと。
- 手動:
  - 「一個前/二個前の発言」質問で、直近2ターンの内容を優先して答えること。
- 合格条件:
  - `uv run ruff format --check src tests`
  - `uv run ruff check src tests`
  - `uv run mypy src tests`
  - `uv run pytest -q`

## 8. 受け入れ基準
- デフォルト設定で2ターン分の短期参照が可能。
- `ACC_SHORT_HISTORY_TURNS` を変えると保持ターン数が変わる。
- CCS のフィールドと API レスポンス契約が変わらない。
- 品質ゲートが全通過する。

## 9. リスク / 対策
- リスク: バッファが長すぎる設定で復唱が増える。
- 対策: デフォルト2を維持し、promptに「必要時のみ参照」と明記する。
- リスク: ポート拡張漏れ。
- 対策: `rg "def decide\("` で全実装更新し、mypyで検知する。

## 10. オープン事項 / 要確認
- なし。

## 11. 実装タスクリスト
- [x] 短期バッファデータ構造の追加
- [x] `AgentPolicyPort` 契約拡張と実装追従
- [x] OpenAI promptへの短期バッファ組み込み
- [x] `ACC_SHORT_HISTORY_TURNS` の設定解決実装
- [x] 単体/結合テスト更新
- [x] 品質コマンド実行

## 12. ドキュメント更新
- [x] `README.md`（必要に応じて）
- [ ] `AGENTS.md`（必要に応じて）
- [x] `docs/task-designs/20260208213056_acc-short-history-buffer-config-phase11.md`

## 13. 承認ログ
- 承認者: shogohasegawa
- 承認日時: 2026-02-08 21:31
- 承認コメント: short history は環境変数で変更可能にし、デフォルト2ターン

## 実装開始条件
- [x] ステータスが `承認済み(approved)` である
- [x] 10. オープン事項が空である
- [x] 受け入れ基準とテスト計画に合意済み
