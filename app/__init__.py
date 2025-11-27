class InvestorWalletBot:
    def __init__(self):
        self.application: Application | None = None
        self.bot: Bot | None = None
        self.initialized: bool = False   # <--- שורה חדשה
