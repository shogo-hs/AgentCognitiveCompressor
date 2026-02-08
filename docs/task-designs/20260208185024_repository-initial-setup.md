# タスク設計書: リポジトリ初期セットアップ

最終更新: 2026-02-08
- ステータス: 完了(done)
- 作成者: Codex
- レビュー: shogohasegawa
- 対象コンポーネント: backend / docs / infra
- 関連: `docs/blue-print/arxiv-2601.11653.md`, `docs/ai/playbooks/python-project-bootstrap.md`, `docs/ai/playbooks/python-uv-ci-setup.md`
- チケット/リンク: 該当なし

## 0. TL;DR
- 目的は、このリポジトリを ACC 実装の土台としてすぐ着手できる状態にすること。
- `python-project-bootstrap` 相当の初期構成を作成し、Hexagonal 構成・設計ルール・`.env.*` 雛形を整備する。
- 続けて `python-uv-ci-setup` 相当の品質ゲート（ruff/mypy/pytest/pre-commit/CI）を導入し、ローカルで実行確認する。
- 既存の canonical / playbook 資産は上書きせず、差分統合で進める。

## 1. 背景 / 課題
- 現状は AI 運用テンプレートが中心で、Python アプリ実装や CI の実行基盤（`pyproject.toml`, `uv.lock`, テスト基盤）が未整備。
- `docs/blue-print/arxiv-2601.11653.md` を実装する前に、開発・検証・CI を回せる最低限の構造が必要。

## 2. ゴール / 非ゴール
### 2.1 ゴール
- Python 実装を置くディレクトリ構造（Hexagonal）を作成する。
- 開発依存・品質ゲート・CI を `uv` 前提で導入し、ローカル検証コマンドが通る状態にする。
- セットアップ結果（作成/更新ファイル、実行コマンド結果）を報告できる状態にする。

### 2.2 非ゴール
- ACC 本体ロジックの実装。
- API エンドポイントやドメイン仕様の詳細設計。
- 本番環境の秘密鍵・実運用値の投入。

## 3. スコープ / 影響範囲
- 変更対象: プロジェクト雛形、品質ゲート設定、CI 設定、環境変数テンプレート。
- 影響範囲: 開発者のローカル開発手順、CI 実行手順。
- 互換性: 既存コードがほぼ無いため破壊的変更リスクは低い。既存 AI 運用ファイルは維持する。
- 依存関係: `uv`, `python3`, GitHub Actions。

## 4. 要件
### 4.1 機能要件
- `src/` 配下に Hexagonal ベースのディレクトリを作成する。
- `docs/rules/`、`docs/architecture/`、`docs/api/`、`docs/task-designs/` の初期文書を整備する。
- `pyproject.toml` と `uv.lock` を整備し、`uv sync --locked --dev` が実行できるようにする。
- `.pre-commit-config.yaml` と `.github/workflows/ci.yml` を整備する。

### 4.2 非機能要件 / 制約
- AGENTS 規約に従い `uv` を使用し、`pip install` は使わない。
- 既存ファイルは破壊的に上書きしない（`--force` 非使用）。
- コミュニケーションとドキュメント記述は日本語中心で行う。

## 5. 仕様 / 設計
### 5.1 全体方針
- 既存 Playbook の流れに沿って、`bootstrap_after_canonical.py` と `bootstrap_python_project.py` を活用して初期構成を生成する。
- CI/品質ゲートは `python-uv-ci-setup` のテンプレートに準拠して追加する。
- 変更後に `uv` ベースの検証コマンドを順に実行してセットアップ完了を確認する。

### 5.2 変更点一覧
| 対象 | 変更内容 | 影響 | 備考 |
| --- | --- | --- | --- |
| `docs/task-designs/20260208185024_repository-initial-setup.md` | 本設計書を追加 | 作業手順の明確化 | 実装前ゲート |
| `src/**`, `tests/**`, `docs/rules/**`, `docs/architecture/**`, `docs/api/**`, `.env.*` | bootstrap スクリプトで初期構成を生成 | 開発基盤追加 | 既存優先で差分作成 |
| `pyproject.toml`, `uv.lock` | uv 依存管理と品質ツール設定を追加 | 依存解決/CI基盤 | 新規作成 |
| `.pre-commit-config.yaml` | pre-commit フックを追加 | ローカル品質ゲート | 新規作成 |
| `.github/workflows/ci.yml` | lint/type/test CI を追加 | PR/Push 品質検証 | 新規作成 |

### 5.3 詳細
#### API
- 今回は API 実装は行わず、`docs/api/index.md` と `docs/api/_endpoint_template.md` を雛形として整備する。

#### UI
- 該当なし。

#### データモデル / 永続化
- 該当なし。

#### 設定 / 環境変数
- `.env.development`, `.env.production`, `.env.example` をテンプレートで作成する。
- `DOTENV_PUBLIC_KEY_*` はプレースホルダのままにし、秘密値は投入しない。

### 5.4 代替案と不採用理由
- 代替案A: 全ファイルを手作業で作成する。
  - 不採用理由: 既存 Playbook/スクリプトがあり、手作業は再現性と DRY を損なう。
- 代替案B: CI 導入を後回しにして構成だけ作る。
  - 不採用理由: AGENTS で CI 必須が明示されており、初期段階で品質ゲートを揃える必要がある。

## 6. 移行 / ロールアウト
- 既存ファイルを保持しつつ不足分を追加する方式で一括適用する。
- ロールバック条件: 既存運用ファイルの想定外上書きや、`uv sync` が恒常的に失敗する場合。
- ロールバック手順: 変更差分を確認し、問題ファイルのみを個別に戻す（破壊的な履歴操作は行わない）。

## 7. テスト計画
- 単体: `tests/unit/test_health_check.py` で最小 smoke test を追加する。
- 結合: 該当なし。
- 手動:
  - `python3 scripts/sync_ai_context.py --check`
  - `uv lock`
  - `uv sync --locked --dev`
  - `uv run pre-commit run --all-files`
  - `uv run ruff format --check src tests`
  - `uv run ruff check src tests`
  - `uv run mypy src tests`
  - `uv run pytest -q`
- LLM/外部依存: 該当なし。
- 合格条件: 上記コマンドが成功し、必要ファイルが作成されていること。

## 8. 受け入れ基準
- リポジトリに Python 実装用ディレクトリと docs 雛形が生成されている。
- `pyproject.toml` / `uv.lock` / `.pre-commit-config.yaml` / `.github/workflows/ci.yml` が存在する。
- `uv` ベースの品質コマンド（ruff/mypy/pytest）が実行可能である。
- 既存 canonical/playbook 関連ファイルが意図せず破壊されていない。

## 9. リスク / 対策
- リスク: bootstrap 実行で既存ファイルが意図せず更新される可能性。
- 対策: `--force` を使わず実行し、更新ファイルを都度 `git diff` で確認する。
- リスク: Python 実行バージョン差異（ローカル 3.13 / 要件 3.12+）による型・依存差。
- 対策: `requires-python >=3.12` で定義し、mypy 設定を 3.12 ベースで固定して検証する。

## 10. オープン事項 / 要確認
- なし。

## 11. 実装タスクリスト
- [x] bootstrap スクリプトで初期構成を生成する
- [x] uv ベースの CI/品質ゲート設定を追加する
- [x] 依存同期と品質チェックを実行する

## 12. ドキュメント更新
- [ ] `README.md`（必要に応じて）
- [ ] `AGENTS.md`（必要に応じて）
- [x] `docs/`（該当ファイルあれば）

## 13. 承認ログ
- 承認者: shogohasegawa
- 承認日時: 2026-02-08 18:51
- 承認コメント: OK

## 実装開始条件
- [x] ステータスが `承認済み(approved)` である
- [x] 10. オープン事項が空である
- [x] 受け入れ基準とテスト計画に合意済み
