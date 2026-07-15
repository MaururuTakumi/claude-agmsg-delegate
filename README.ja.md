# claude-agmsg-delegate

[English](README.md) · [AI向け手順](AGENTS.md) · [llms.txt](llms.txt)

Codex Desktopから[agmsg](https://github.com/fujibee/agmsg)経由でClaude Fable／Sonnetへ、設計レビュー・実装案・テスト案を安全に委譲するCodex Skillです。

Claudeにはツールを渡しません。実ファイル編集、コマンド、テスト、最終判断は主担当Codexが行います。

## AIにそのまま渡す

Codexへ次を貼り付けてください。

```text
https://github.com/MaururuTakumi/claude-agmsg-delegate を一時ディレクトリへcloneしてください。
AGENTS.mdとREADME.ja.mdを最後まで読み、fixtureテストと ./install.sh --dry-run を実行してください。
すべて成功したら、現在のCodexユーザーへSkillをインストールしてください。
インストール中はClaudeを呼び出さず、モデルクレジットを消費しないでください。
最後にdelegate_claude.pyのdry-runでteam、sender、receiver、model、tools policyを確認して報告してください。
```

## 手動インストール

前提:

- macOSまたはLinux
- Python 3.10+
- Codex
- Claude Code
- `~/.agents/skills/agmsg`へインストール済みのagmsg
- CodexとClaudeが参加したagmsg team

```bash
npx agmsg
git clone https://github.com/MaururuTakumi/claude-agmsg-delegate.git
cd claude-agmsg-delegate
make test
./install.sh --dry-run
./install.sh
```

インストール後、Codexを再起動してください。

## 使い方

```text
$claude-agmsg-delegate Fableにこの設計をレビューさせて
$claude-agmsg-delegate Sonnetに実装案とテスト案を考えさせて
```

自然文でも利用できます。

```text
Fableにこの設計をレビューさせて
Sonnetへ実装とテストの方針を相談して
```

- Fable: 設計、計画、tradeoff、独立レビュー
- Sonnet: 実装案、edge case、テスト設計
- Codex: ローカル確認、編集、実行、テスト、最終判断

## 60秒を超えた場合

同期waitが終わってもworkerは継続し、`status: running`を返します。同じ依頼を再送せず、返されたjob IDを回収してください。

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/claude-agmsg-delegate/scripts/delegate_claude.py" collect \
  --job-id <job_id> \
  --wait 60
```

jobは`~/.cache/codex/claude-agmsg-delegate/jobs/`へ保存され、回収は冪等です。

## 安全性

- Claudeは`--safe-mode --tools ""`
- permission bypassなし
- secretらしい依頼は送信前に拒否
- agmsg DB／teamファイルへ直接アクセスしない
- 既存agmsg role／hookを自動変更しない
- 既定のモデル予算上限は1回`$1.00`
- install／testではClaudeを呼ばず課金しない

詳しいCLI、routing、result JSON、troubleshootingは[英語README](README.md)を参照してください。

## 開発

```bash
make test
```

テストはfake agmsgとfake Claudeだけを使い、実メッセージや課金を発生させません。

## ライセンス

[MIT](LICENSE)
