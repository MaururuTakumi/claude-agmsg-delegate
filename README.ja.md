# claude-agmsg-delegate

[English](README.md) · [AI向け手順](AGENTS.md) · [llms.txt](llms.txt)

Codex Desktopから[agmsg](https://github.com/fujibee/agmsg)経由でClaude
Fable／Sonnetへ、設計レビュー・テスト案・ユーザー承認済みのworkspace
実装を委譲するCodex Skillです。

Claudeの画面を見る必要はありません。tmuxペイン、既存の対話セッション、
常駐monitorも不要です。Fableと相談だけのSonnetはplan modeで対象project
directoryを`Read,Glob,Grep`できます。明示的なSonnet実装では編集もでき、Codexがdiffをレビューして
テストした後にだけ採用します。

課金経路はサブスク限定・fail-closedです。Claude Codeが有料Claude.ai OAuthを使っていると確認できた場合だけ推論し、API key、bearer token、custom base URL、Bedrock、Vertex、Foundry、Mantle経路は推論前に拒否します。API経路へのfallbackはありません。

## AIにそのまま渡す

Codexへ次を貼り付けてください。

```text
https://github.com/MaururuTakumi/claude-agmsg-delegate を一時ディレクトリへcloneしてください。
AGENTS.mdとREADME.ja.mdを最後まで読んでください。
make testと ./install.sh --dry-run を実行してください。
成功したら、Claudeやagmsgの準備状況にかかわらず、まず ./install.sh でofflineのSkill本体をインストールしてください。既存版の更新ではdry-runを確認してから --force を使ってください。
実際に委譲を使う対象projectへ移動し、installed delegate_claude.py doctorを実行してください。doctorはmodel実行、agmsg送信、job state作成、network access、設定変更をしてはいけません。
Claude Codeが有料Claude.aiサブスクでlogin済みで、API keyやcloud provider認証が有効でないことを確認してください。
最終Skill dry-runの前に、~/.agents/skills/agmsg/scripts/ のwhoami.sh、send.sh、api.shが存在し、実行可能か確認してください。公式agmsg 1.1.8以降にはapi.shが含まれます。これはlocal read-only JSONL readerで、Anthropic API呼び出しではありません。
agmsgが未導入または古い場合は停止し、npx agmsgの実行、team参加、delivery mode選択の前に私へ明示承認を求めてください。設定を推測したりagmsgのファイルを直接編集したりしないでください。
承認後はagmsgを導入し、Claude委譲を実際に使う対象projectへ移動してください。既存teamがなければ、<対象project名>-team / codexを候補として表示し、確認を待ってからjoin.shを実行してください。deliveryは別に確認し、1) turnを推奨、2) offも選択可、monitor／bothは選択禁止です。空入力またはEnterはturnです。提供されるwhoami.sh、join.sh、delivery.shの手順だけを使い、確認のためだけに一時clone先をteamへ参加させないでください。Claude modelを実行せず、対象projectから最終dry-runへ戻ってください。
install中はClaude modelを実行せず、model usageを消費しないでください。
delegate_claude.py --versionが0.3.0であることを確認してください。
最後にdelegate_claude.pyの--dry-runで認証、team、sender、receiver、model、subscription-only policy、execution mode、tool allowlist、review requirementを確認してください。
--dry-runはread-onlyのclaude auth statusを実行して構いませんが、agmsg job送信とmodel inferenceは行わないでください。
```

## 前提

- macOSまたはLinux
- Python 3.9+
- Codex
- Claude Code
- Claude Pro、Max、Team、またはseat-based Enterpriseの有料サブスク
- API keyではなく`claude auth login`で認証済みのClaude Code
- `~/.agents/skills/agmsg`へインストール済みのagmsg
- 現在のprojectが所属し、team名を一意に推測できるagmsg team

従量課金を完全にゼロにしたい場合は、Claudeの **Settings → Usage → Extra usage / usage credits** も必ずOFFにしてください。wrapperは現在の認証経路を検証・強制できますが、公式Claude CLIがこのaccount設定を公開していないため、すでにONの追加利用を変更することはできません。

認証確認:

```bash
claude auth login
claude auth status --json
```

許可される状態は次のとおりです。

```json
{
  "loggedIn": true,
  "authMethod": "claude.ai",
  "apiProvider": "firstParty",
  "subscriptionType": "max"
}
```

`subscriptionType`は`pro`、`team`、`enterprise`でも構いません。`ANTHROPIC_API_KEY`、`ANTHROPIC_AUTH_TOKEN`、custom Anthropic base URL、provider選択変数、`CLAUDE_CODE_OAUTH_TOKEN`がある場合は停止します。このSkillではlocalの`/login`サブスクだけを許可します。

Anthropic公式の[認証優先順位](https://code.claude.com/docs/en/authentication)、[サブスク利用時のcost表示](https://code.claude.com/docs/en/costs)、[Pro／MaxでClaude Codeを使う説明](https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan)、現在の[`claude -p`サブスク利用案内](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan)も参照してください。

## 手動インストール

agmsgの導入、team参加、delivery mode選択はlocal agentの役割と配信設定を変更します。AIに作業させる場合、`npx agmsg`を実行する前に必ず明示承認を求めさせてください。

```bash
git clone https://github.com/MaururuTakumi/claude-agmsg-delegate.git
cd claude-agmsg-delegate
make test
./install.sh --dry-run
./install.sh
```

これでClaudeやagmsgが未準備でもSkill本体は導入済みになります。Claude委譲を
使いたい対象projectへ戻り、変更を行わない診断を実行してください。

```bash
python3 ~/.codex/skills/claude-agmsg-delegate/scripts/delegate_claude.py doctor
```

`doctor`はPython、installed Skill、Claude Codeの標準install先、有料サブスク
認証、agmsg、local pathを確認します。model実行、agmsg送信、job state作成、
network access、設定変更は行いません。`SKILL_NOT_INSTALLED`、
`CLAUDE_BIN_NOT_FOUND`、`CLAUDE_BIN_OUTSIDE_PATH`、`AGMSG_NOT_INSTALLED`、
`AGMSG_OUTDATED`などの安定したcodeで原因を区別します。Claudeが
`~/.local/bin/claude`にあってPATH外でも、自動発見して絶対pathをworkerへ固定します。

確認のためだけにSkill repoを無関係なteamへ参加させません。doctorがagmsgの
未導入／旧版を報告した場合は停止し、明示承認を得てから実行します。

```bash
npx agmsg
```

既存teamがない新しい端末では、`<対象project名>-team / codex`（例：`movacal-team / codex`）が通常の候補です。AIはこの2値を表示して確認を待ちます。join後のdeliveryは`1`またはEnterで推奨の`turn`、手動確認にしたい場合だけ`2`の`off`を選びます。Codexでは`monitor`／`both`を選びません。

インストール後、Codexを再起動して新しいタスクを開始してください。更新前から
開いているタスクには、古いSkill手順が残る場合があります。

## 使い方

```text
$claude-agmsg-delegate Fableにこの設計をレビューさせて
$claude-agmsg-delegate Sonnetに実装案とテスト案を考えさせて
$claude-agmsg-delegate Sonnetにこの変更を実装させ、Codexでdiffをレビューしてテストして
```

自然文でも利用できます。

```text
Fableにこの設計をレビューさせて
Sonnetへ実装とテストの方針を相談して
```

- Fable: 設計、計画、tradeoff、独立レビュー
- Sonnet: 実装案、edge case、テスト設計、ユーザー承認済みworkspace編集
- Codex: orchestration、diffレビュー、command、テスト、統合、最終判断

## 仕組み

```text
Codex Desktop
  ├─ claude auth status --json
  │    └─ claude.ai + firstParty + 有料subscriptionだけ許可
  └─ agmsg delegate_request { job_id, model, role, task }
       └─ detached worker
            ├─ 認証をもう一度確認
            ├─ advisory read: Read,Glob,Grep + plan
            ├─ Sonnet実装: --workspace-write
            │    └─ Read,Edit,Write,Glob,Grep + acceptEdits
            ├─ 推論後も再確認し、認証変化時はresultを破棄
            └─ agmsg delegate_response { job_id, status, result }
                 └─ Codexがdiffレビュー・テスト・最終判断
```

agmsgはjobの配送・記録・相関に使います。どの課金方法になるかはClaude Codeの認証が決めます。tmuxはこの経路に含まれません。default mailboxは`codex-delegate → claude-delegate`で、Ghostty／Gdashの可視`codex → claude` delivery loopとは分離されます。

wrapperだけがagmsgの`whoami.sh`、`send.sh`、公式のlocal read-only
`api.sh`を呼びます。Claudeにはagmsg toolを渡さず、DBやteamファイルを
直接読みません。`api.sh`はlocal JSONLを返すだけで、Anthropic APIやAPI
課金とは無関係です。既存環境の`list-ids.sh`も互換対応しますが、新規導入には不要です。

全job共通の起動条件:

```text
--print --safe-mode --setting-sources "" --output-format stream-json --verbose --no-session-persistence
```

advisoryは`--tools "Read,Glob,Grep" --permission-mode plan`、Sonnet workspace実装は
`--tools "Read,Edit,Write,Glob,Grep" --permission-mode acceptEdits`を追加します。
どちらもBashとpermission bypassは使いません。

version `0.3.0`のruntime contractは`contract_version=2`です。Fable／Sonnetの
resultを採用する前に、Claude Codeの`stream-json`から最低1件の`Read`実行を
確認します。成功時は`workspace_grounded: true`とproject-relativeな
`files_read`を返します。Read証跡がない、またはproject外のpathが観測された
resultは破棄します。

## Sonnetにworkspaceを実装させる

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/claude-agmsg-delegate/scripts/delegate_claude.py" run \
  --model sonnet \
  --role implementer \
  --workspace-write \
  --task "現在のGit workspaceへこの変更を実装し、無関係なfileは変更しないでください。" \
  --timeout 120
```

Codexは実行前の`git status --short`を確認し、完了後に
`git status --short`と`git diff --`をレビューします。無関係な変更を拒否し、
関連テストをCodex側で実行してから採用します。`--workspace-write`はGit
worktree内のSonnet implementerだけが使えます。

## dry-run

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/claude-agmsg-delegate/scripts/delegate_claude.py" run \
  --model fable \
  --task "Review this proposal." \
  --dry-run
```

`--dry-run`はlocalのread-only認証確認だけを実行します。model inference、agmsg送信、job state作成は行いません。

## 60秒を超えた場合

同期waitが終わってもworkerは継続し、`status: running`を返します。同じ依頼を再送せず、返されたjob IDを回収してください。
`worker_stage`と`running_seconds`で進捗を区別できます。workerがterminal
stateを書かず終了した場合、次のcollectで即座に`failed`へ変わります。

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/claude-agmsg-delegate/scripts/delegate_claude.py" collect \
  --job-id <job_id> \
  --wait 60
```

jobは`~/.cache/codex/claude-agmsg-delegate/jobs/`へ保存され、回収は冪等です。常駐monitorは不要です。

成功時には課金経路の検証結果も返します。Claude CLIが内部で返す`total_cost_usd`や`cost_usd`などの金額換算値は、result、agmsg response、保存state、terminal outputから除外し、Codexも表示・言い換え・転送しません。確認済みのsubscription経路だけを報告します。

```json
{
  "status": "completed",
  "delegate_version": "0.3.0",
  "contract_version": 2,
  "requested_model": "sonnet",
  "actual_model": "claude-sonnet-5",
  "execution_mode": "workspace_write",
  "tools": ["Read", "Edit", "Write", "Glob", "Grep"],
  "permission_mode": "acceptEdits",
  "review_required": true,
  "workspace_grounded": true,
  "files_read": ["src/example.ts"],
  "billing_mode": "subscription",
  "auth_method": "claude.ai",
  "api_provider": "firstParty",
  "subscription_type": "max",
  "result": "..."
}
```

`requested_model`だけでなく`actual_model`も確認してください。subscription利用時のlocal推定ドル表示は請求額ではないため、result contractから除外しています。

## 安全性と課金境界

- parent processがagmsg送信前にサブスク認証を確認
- detached workerが推論直前にもう一度確認
- 推論後にも認証を再確認し、変化していたらresultを破棄
- API key／auth token／custom base URL／cloud provider経路はfail-closed
- Claudeへ渡すenvironmentは最小allowlistで、将来追加される未知のprovider変数を継承しない
- `--safe-mode --setting-sources ""`でuser／project／local settingsを読み込まない。admin-managed policyは残るため、前後のauth checkで検証
- subscription認証失敗時やlimit到達時のAPI credential fallbackなし
- Fable／advisory Sonnetは対象project directory内で
  `--safe-mode --tools "Read,Glob,Grep" --permission-mode plan`。file変更とcommand実行は禁止
- 明示的なSonnet implementerだけがGit workspace内で
  `Read,Edit,Write,Glob,Grep`と`acceptEdits`を使用
- workspace-writeは`review_required=true`を返し、Codexが実diffをレビュー、
  無関係な変更を拒否、テストを実行して最終判断
- Bash、install、deploy、push、無関係なpathへのaccessは許可しない
- agmsg teamはmessage routingだけを決め、read範囲は対象project directoryと
  Claudeのtool／permission policyで制限する。書き込みはGit worktree必須
- worker内からusage creditsを有効化するcommandとimplicit 1M context variantを無効化
- account側のExtra usage / usage creditsは別途OFFが必要
- permission bypassなし
- secretらしい依頼は送信前に拒否
- agmsg DB／teamファイルへ直接アクセスしない
- 既存agmsg role／hookを自動変更しない
- install／testはClaude modelを実行せず課金しない

## 更新

最新版をpullしてテストした後、`--force`で更新します。

```bash
git pull --ff-only
make test
./install.sh --dry-run --force
./install.sh --force
python3 ~/.codex/skills/claude-agmsg-delegate/scripts/delegate_claude.py --version
```

以前のinstalled Skillは削除せず、
`~/.codex/skill-backups/claude-agmsg-delegate/`へ移動します。旧installerが
`~/.codex/skills/claude-agmsg-delegate.backup-*`へ作ったbackupも、同じ
backup rootへ内容を保ったまま自動移動します。名前の衝突時は連番を付け、
既存backupを上書きしません。

`~/.codex/skills/`内に、installerが作っていない同名Skillが残る場合は、
該当pathとversionを一覧表示してstatus 4で停止します。そのdirectoryは
自動削除・移動しません。不要なcopyだけを`skills/`外へ移して再実行し、
Codexを再起動して新しいタスクを開始してください。

## よくあるエラー

### 更新後も古いSkillが使われる

上記の`./install.sh --force`を再実行し、表示されたversionが`0.3.0`である
ことを確認してください。installerは旧backupをSkill探索対象外へ移動し、
未知の同名copyがあればpathとversionを表示して停止します。現在開いている
タスクは更新前の手順を保持する場合があるため、Codexを再起動した後、
必ず新しいタスクから利用してください。

### `subscription-only policy blocked ...`

表示された変数を削除し、有料Claude.ai accountだけでloginし直します。

```bash
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL CLAUDE_CODE_OAUTH_TOKEN
claude auth logout
claude auth login
claude auth status --json
```

Claude settingsの`apiKeyHelper`やprovider選択設定も削除してください。別課金経路へ自動fallbackはしません。

### `status: running`

同期waitが終了しています。`worker_stage`と`running_seconds`を確認し、
返された`--wait 60`付き`collect_command`を使ってください。同じ依頼は再送しません。
workerが既に終了していれば、collectはTTLを待たず`failed`を返します。

### Fableに`Read,Glob,Grep`があるのに別の指示が`toolsなし`と言う

正常なのは`Read,Glob,Grep`です。`toolsなし`は古い0.1契約なので、tool-freeへ
戻したり今回だけの許可を求めたりしません。最新版を再インストールしてCodexを
再起動し、次を確認します。

```bash
python3 ~/.codex/skills/claude-agmsg-delegate/scripts/delegate_claude.py --version
```

期待値は`0.3.0`で、dry-runには`contract_version: 2`が出ます。実jobがfileを
読んだ証明はdry-runではなく、completed resultの`workspace_grounded: true`と
空でないproject-relativeな`files_read`です。

### `required agmsg script is missing`

最終dry-runを止め、Claude modelは実行しません。AIはagmsgの導入とteam／delivery設定がlocal agent routingを変更することを説明し、`npx agmsg`の前に明示承認を求めます。
公式agmsgの`api.sh`がlocal message readerです。存在しない場合は承認後に
agmsgを更新し、非公開の`list-ids.sh`を作成・取得しないでください。

承認後は次の順序で進めます。

1. `npx agmsg`を実行
2. Claude委譲を実際に使う対象projectへ移動。一時Skill cloneを確認のためだけにteam参加させない
3. `~/.agents/skills/agmsg/scripts/whoami.sh`で対象project identityを確認
4. 未参加ならteam名とagent名を確認してから`join.sh`を実行
   - 既存teamがなければ`<対象project名>-team / codex`を候補表示し、確認後に作成
5. `1) turn`（推奨、Enterでも可）または`2) off`を選んでもらってから`delivery.sh`を実行。raw promptに表示されても`monitor`／`both`は選ばない
6. 対象projectから同じ`delegate_claude.py ... --dry-run`へ戻る

agmsgのconfig、database、teamファイルは直接編集せず、team、identity、delivery modeを推測しません。

### 初回promptに`turn`、`off`、`monitor`が表示された

このCodex workflowでは`1`またはEnterで推奨の`turn`を選びます。手動でinbox確認したい場合だけ`2`の`off`を選び、`monitor`／`both`は選びません。

### 従量課金を完全に避けたい

Claude **Settings → Usage → Extra usage / usage credits** がOFFであることも確認してください。サブスク枠を使い切ったら、追加creditsを有効化せずresetを待ちます。

## 開発

```bash
make test
make check
```

テストはfake agmsgとfake Claudeだけを使います。有料サブスク受理、
API/provider拒否、worker開始後の認証変化、job相関、timeout／dead worker回収、
Read証跡、project外path拒否、version contract、大きなresult、Sonnet
workspace編集、file-tool allowlist、review-required出力を
検証し、実modelや課金は発生させません。

## ライセンス

[MIT](LICENSE)
