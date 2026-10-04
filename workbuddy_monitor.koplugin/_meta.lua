local _ = require("gettext")
return {
    fullname = _("WorkBuddy Monitor"),
    description = _([[Pull the PC-side WorkBuddy status (credits, expiring points,
running tasks) as a cyberpunk cover image every 3 minutes over the local
network and show it on the Kindle. Agent-agnostic: it only reads what the
PC-side wb-bridge.py serves.]]),
}
