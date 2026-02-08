# タスク設計書: 会話品質整合と日本語想起改善 Phase 10 実装

最終更新: 2026-02-08
- ステータス: 完了(done)
- 作成者: Codex
- レビュー: shogohasegawa
- 対象コンポーネント: backend / docs
- 関連: `docs/task-designs/20260208204341_ccs-semantic-fallback-phase9.md`, `src/acc/application/use_cases/acc_multiturn_control_loop.py`, `src/acc/adapters/outbound/in_memory_acc_components.py`, `src/acc/adapters/outbound/openai_chat_adapters.py`
- チケット/リンク: `https://zenn.dev/meson_tech_blog/articles/implement-acc-agent`, `https://github.com/edom18/ACC_Agent`

## 0. TL;DR
- 現状は `Decide` が最新ユーザー質問を直接受け取らないため、CCS 依存の定型応答に偏りやすい。
- 参照実装に合わせて「質問起点の応答生成」「想起→選別の日本語適合」「ACC用/Agent用モデル分離」を導入する。
- `AgentPolicyPort` に `interaction_signal` を渡す設計へ拡張し、OpenAI プロンプトで「質問に先に答える」規律を明示する。
- in-memory 想起のトークン化を日本語対応し、無関係 Artifact の機械的補充をやめて関連性ノイズを減らす。

## 1. 背景 / 課題
- 実行ログ上、同型応答の反復（家族情報への再言及）と、質問への直接回答不足が発生している。
- `src/acc/application/use_cases/acc_multiturn_control_loop.py` では `agent_policy.decide` に最新 `user_input` が渡らず、生成器が質問の粒度を取りこぼしうる。
- `src/acc/adapters/outbound/in_memory_acc_components.py` の `_normalize_tokens` は英数字のみで、日本語入力時に想起・選別の重なり判定が弱い。
- 参照記事/実装では、Qualification Gate と役割分離（CCM と Agent）を強調しており、現状実装はこの点が弱い。

## 2. ゴール / 非ゴール
### 2.1 ゴール
- `Decide` が毎ターンの最新質問を直接参照し、質問先行で回答を返せること。
- 日本語入力で Recall/Qualification の関連判定が働き、`Qualification=0` の過剰発生を抑えること。
- OpenAI 利用時に `OPENAI_COMPRESSOR_MODEL` と `OPENAI_AGENT_MODEL` を分離設定可能にすること（未設定時は既存互換）。
- 既存 API 契約を壊さず、ユニットテストで回帰を防ぐこと。

### 2.2 非ゴール
- Vector DB 導入や永続ストレージ移行。
- UI の新規機能追加。
- メモリカテゴリ（episodic/gist/entities など）の仕様全面改訂。

## 3. スコープ / 影響範囲
- 変更対象: ポート定義、制御ループ、OpenAI/インメモリ各アダプタ、テスト、README。
- 影響範囲: 応答品質、想起/選別品質、OpenAI モデル設定運用。
- 互換性: API レスポンス互換維持。内部インタフェース（`AgentPolicyPort`）は変更。
- 依存関係: 追加ライブラリなし。

## 4. 要件
### 4.1 機能要件
- `AgentPolicyPort.decide` に `interaction_signal: TurnInteractionSignal` を追加する。
- `ACCMultiturnControlLoop.run_turn` から `decide` へ最新 `interaction_signal` を渡す。
- `OpenAIAgentPolicyAdapter` のプロンプトに以下を追加する。
  - 最新質問に最初に回答する。
  - 既出の自己紹介復唱は、質問解決に必要な場合のみ行う。
  - 不確実性は `uncertainty_signal` に従って明示する。
- in-memory 想起/選別で日本語を含むトークン抽出を実装し、重なり 0 の候補を機械的に埋めない。
- `create_app` のデフォルト依存で以下環境変数をサポートする。
  - `OPENAI_COMPRESSOR_MODEL`
  - `OPENAI_AGENT_MODEL`
  - いずれも未設定時は `OPENAI_MODEL` へフォールバック。

### 4.2 非機能要件 / 制約
- `ruff` / `mypy` / `pytest` を通す。
- `.env*` の実ファイル編集は行わない。
- Hexagonal の依存方向を維持する（domain -> ports -> adapters）。

## 5. 仕様 / 設計
### 5.1 全体方針
- 質問適合性の欠落は `Decide` 入力欠落が主因のため、ポート契約を最小拡張して根治する。
- 想起品質は「日本語非対応トークン化 + 関連性ゼロの補充」が主因のため、言語依存ノイズを減らす。
- 参照実装の方針（Qualification Gate とモデル役割分離）を既存構成に無理なく移植する。

### 5.2 変更点一覧
| 対象 | 変更内容 | 影響 | 備考 |
| --- | --- | --- | --- |
| `src/acc/ports/outbound/agent_policy_port.py` | `decide` シグネチャに `interaction_signal` 追加 | 内部契約変更 | 全アダプタ追従必須 |
| `src/acc/application/use_cases/acc_multiturn_control_loop.py` | `decide` 呼び出しへ最新シグナル渡し | 応答関連性向上 | |
| `src/acc/adapters/outbound/openai_chat_adapters.py` | policy prompt に質問優先規律追加、入力 payload へ `interaction_signal` 追加 | OpenAI 応答品質改善 | |
| `src/acc/adapters/outbound/in_memory_acc_components.py` | 日本語対応トークン化、Recall 補充ロジック見直し、`EchoAgentPolicyAdapter` 追従 | テスト/ローカル品質改善 | |
| `src/acc/adapters/inbound/http/app.py` | compressor/agent モデル env 分離 | 運用柔軟性向上 | 後方互換 |
| `tests/unit/test_acc_multiturn_control_loop.py` ほか | 新シグネチャ・日本語想起挙動のテスト追加/更新 | 回帰防止 | |
| `README.md` | 追加環境変数と役割分離方針を追記 | ドキュメント整合 | |

### 5.3 詳細
#### API
- エンドポイント仕様は変更しない。
- 応答本文の品質改善のみを狙う。

#### UI
- 変更なし。

#### データモデル / 永続化
- CCS スキーマは変更なし。
- in-memory 想起アルゴリズムのみ変更。

#### 設定 / 環境変数
- 追加（任意）: `OPENAI_COMPRESSOR_MODEL`, `OPENAI_AGENT_MODEL`
- 既存互換: 未設定時 `OPENAI_MODEL` を使用。

### 5.4 代替案と不採用理由
- 代替案A: AgentPolicy のプロンプトだけ修正し、`interaction_signal` は渡さない。
  - 不採用理由: 質問文を直接参照できず、再発余地が残る。
- 代替案B: Recall を完全にベクトル検索へ置換する。
  - 不採用理由: 今回は品質改善の最短経路が目的で、依存追加と移行コストが高い。

## 6. 移行 / ロールアウト
- 段階リリース不要（内部実装の改善）。
- ロールバック条件: 応答品質が悪化、または既存テストが継続的に不安定化する場合。
- ロールバック手順: `AgentPolicyPort` 変更を戻し、想起ロジック改善を個別に再適用。

## 7. テスト計画
- 単体:
  - `AgentPolicyPort` 拡張に伴う呼び出し整合。
  - 日本語テキストで `_normalize_tokens` が重なり判定に使えること。
  - Recall が無関係候補で埋まらないこと。
- 結合:
  - `ChatSessionUseCase` を通して応答が生成され、既存 API テストが維持されること。
- 手動:
  - 実際の日本語相談文（質問連続）で「質問への直接回答」が先頭に出ることを確認。
- LLM/外部依存:
  - CI は in-memory テスト中心。OpenAI 直接呼び出しはモック/非依存。
- 合格条件:
  - `uv run ruff format --check src tests`
  - `uv run ruff check src tests`
  - `uv run mypy src tests`
  - `uv run pytest -q`

## 8. 受け入れ基準
- 質問文を入力したターンで、応答が質問内容を直接扱う（定型謝辞の反復が主文にならない）。
- 日本語入力でも Recall/Qualification の関連判定が機能する。
- `OPENAI_COMPRESSOR_MODEL` / `OPENAI_AGENT_MODEL` が有効で、未設定時は既存挙動を維持する。
- 全テストと品質ゲートが通る。

## 9. リスク / 対策
- リスク: ポート変更で既存アダプタ実装漏れが起きる。
- 対策: `rg "def decide\("` で全実装を網羅更新し、型チェックで検出する。
- リスク: 日本語トークン化の過検出により想起ノイズが残る。
- 対策: 記号除去・重複除去・最小長制約を入れ、テストで境界ケースを固定する。

## 10. オープン事項 / 要確認
- なし。

## 11. 実装タスクリスト
- [x] `AgentPolicyPort` と関連実装のシグネチャ拡張
- [x] OpenAI policy prompt の質問優先ルール追加
- [x] in-memory 想起/選別の日本語対応改善
- [x] OpenAI モデル環境変数の役割分離対応
- [x] 単体/結合テスト更新
- [x] 品質コマンド実行

## 12. ドキュメント更新
- [x] `README.md`（必要に応じて）
- [ ] `AGENTS.md`（必要に応じて）
- [x] `docs/task-designs/20260208210520_acc-conversation-quality-alignment-phase10.md`

## 13. 承認ログ
- 承認者: shogohasegawa
- 承認日時: 2026-02-08 21:17
- 承認コメント: 元のコンセプトに沿って実装を進める

## 実装開始条件
- [x] ステータスが `承認済み(approved)` である
- [x] 10. オープン事項が空である
- [x] 受け入れ基準とテスト計画に合意済み
