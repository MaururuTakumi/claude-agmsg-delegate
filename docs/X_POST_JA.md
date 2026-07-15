1. CodexにこのURLを渡してください。
https://github.com/MaururuTakumi/claude-agmsg-delegate

2. Claude Codeへ有料Claude.aiサブスクでloginし、Settings → UsageのExtra usage / usage creditsをOFFにしてください。

3. Codexへ「cloneしてAGENTS.mdを読み、テスト→dry-run→Skillをインストールして。API/provider認証なら停止して」と頼んでください。

4. 初回だけagmsg設定を聞かれます。既存teamがなければ「<対象project名>-team / codex」、deliveryは「1」またはEnterのturnを選んでください。monitorは選びません。

5. Codexを再起動し、「Fableに設計レビュー」「Sonnetに実装して。完了後にdiffをレビューして」と頼んでください。

これでClaudeの画面やtmuxを開かず、Codexからagmsg経由でサブスクのFable／Sonnetを呼べるようになります。
