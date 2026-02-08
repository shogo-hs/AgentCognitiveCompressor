# タスク設計書: パッケージパスを src/acc へ変更

最終更新: 2026-02-08
- ステータス: 完了(done)
- 作成者: Codex
- レビュー: shogohasegawa
- 対象コンポーネント: backend / docs
- 関連: `docs/task-designs/20260208185024_repository-initial-setup.md`
- チケット/リンク: 該当なし

## 0. TL;DR
- 要望どおり Python パッケージディレクトリを `src/agent_cognitive_compressor` から `src/acc` に変更する。
- import 文、テスト、アーキテクチャドキュメント内のパス表記を新パスに合わせて更新する。
- `pyproject.toml` に Hatchling の配布対象設定を追加し、プロジェクト名を維持したまま `src/acc` をビルド対象にする。

## 1. 背景 / 課題
- 現在のパッケージパスが長いため、実装・import 記述の簡素化のため `src/acc` へ統一したい。
- 既存の `project.name` は `agent-cognitive-compressor` のため、単純なディレクトリ名変更だけではビルド対象解決が壊れる可能性がある。

## 2. ゴール / 非ゴール
### 2.1 ゴール
- 実体パッケージを `src/acc` に移設する。
- コード/テスト/ドキュメントの参照を `acc` 基準へ更新する。
- `uv run` 系品質コマンド（ruff/mypy/pytest）を全て成功させる。

### 2.2 非ゴール
- プロジェクト名（`agent-cognitive-compressor`）の変更。
- ドメインロジックの追加・変更。

## 3. スコープ / 影響範囲
- 変更対象: `src/`, `tests/`, `docs/rules/`, `docs/architecture/`, `pyproject.toml`。
- 影響範囲: import パス、パッケージビルド設定、設計ドキュメントの例示パス。
- 互換性: 旧 import パスは無効化される（内部コードのみのため影響は限定的）。
- 依存関係: `hatchling` のパッケージ探索設定。

## 4. 要件
### 4.1 機能要件
- ディレクトリを `src/acc` へ変更する。
- テスト import を `from acc...` へ変更する。
- `pyproject.toml` に `tool.hatch.build.targets.wheel` を追加し、`src/acc` を明示する。

### 4.2 非機能要件 / 制約
- 既存規約どおり `uv` ベースで検証する。
- 変更は必要最小限に留め、不要ファイル追加は行わない。

## 5. 仕様 / 設計
### 5.1 全体方針
- 物理リネーム + 参照更新 + ビルド設定追従の3点を一括実施する。
- 実施後に pre-commit と ruff/mypy/pytest で回帰確認する。

### 5.2 変更点一覧
| 対象 | 変更内容 | 影響 | 備考 |
| --- | --- | --- | --- |
| `src/agent_cognitive_compressor/` | `src/acc/` へリネーム | import パス変更 | 実体移設 |
| `tests/unit/test_health_check.py` | import を `acc` に変更 | テスト実行 | 必須追従 |
| `docs/rules/code_architecture/README.md` | パス表記更新 | ドキュメント整合 | 例示修正 |
| `docs/architecture/hexagonal-architecture.md` | パス表記更新 | ドキュメント整合 | 例示修正 |
| `pyproject.toml` | hatch build ターゲット設定追加 | 配布/同期安定化 | `src/acc` 指定 |

### 5.3 詳細
#### API
- 該当なし。

#### UI
- 該当なし。

#### データモデル / 永続化
- 該当なし。

#### 設定 / 環境変数
- 該当なし。

### 5.4 代替案と不採用理由
- 代替案A: `project.name` も `acc` に変更する。
  - 不採用理由: 要望はディレクトリ変更であり、公開パッケージ名の変更影響が大きい。
- 代替案B: 旧ディレクトリを残して新規に `src/acc` を追加する。
  - 不採用理由: 実装重複を招き、DRYに反する。

## 6. 移行 / ロールアウト
- 一括変更して同一PR内で完結させる。
- ロールバック条件: `uv sync` や `pytest` が修正不能な状態で失敗する場合。
- ロールバック手順: 変更差分を個別に戻し、旧パスへ復帰する。

## 7. テスト計画
- 単体: `uv run pytest -q`
- 結合: 該当なし。
- 手動:
  - `uv run pre-commit run --all-files`
  - `uv run ruff format --check src tests`
  - `uv run ruff check src tests`
  - `uv run mypy src tests`
- LLM/外部依存: 該当なし。
- 合格条件: 上記コマンドがすべて成功すること。

## 8. 受け入れ基準
- `src/acc` が存在し、`src/agent_cognitive_compressor` が存在しない。
- テスト import が `acc` を参照している。
- ドキュメント内の該当パスが `src/acc` へ更新されている。
- 品質コマンドが全て成功する。

## 9. リスク / 対策
- リスク: ビルド対象パッケージが解決できず `uv sync` が失敗する。
- 対策: `pyproject.toml` に hatch の wheel パッケージパスを明示設定する。
- リスク: 参照漏れにより import エラーが残る。
- 対策: `rg` で旧パス文字列を全検索してゼロ件確認する。

## 10. オープン事項 / 要確認
- なし。

## 11. 実装タスクリスト
- [x] パッケージディレクトリを `src/acc` へ変更
- [x] import / ドキュメント / ビルド設定を追従更新
- [x] 品質コマンドを実行して結果確認

## 12. ドキュメント更新
- [ ] `README.md`（必要に応じて）
- [ ] `AGENTS.md`（必要に応じて）
- [x] `docs/`（該当ファイルあれば）

## 13. 承認ログ
- 承認者: shogohasegawa
- 承認日時: 2026-02-08 19:01
- 承認コメント: OK

## 実装開始条件
- [x] ステータスが `承認済み(approved)` である
- [x] 10. オープン事項が空である
- [x] 受け入れ基準とテスト計画に合意済み
