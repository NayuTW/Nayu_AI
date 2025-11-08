        # Initialize CodeAgent
        self.agent = CodeAgent(
            tools=self.tools,
            model=self.model,
            max_steps=15,
            return_code=False,  # Don't require final_answer() call
            additional_authorized_imports=[
                "requests", "json", "re", "time", "datetime",
                "bs4", "duckduckgo_search", "readability", "html2text"
            ]
        )
        
            # Reinitialize the main CodeAgent with updated tools
            self.agent = CodeAgent(
                tools=self.tools,
                model=self.model,
                max_steps=15,
                return_code=False,  # Don't require final_answer() call
                additional_authorized_imports=[
                    "requests", "json", "re", "time", "datetime",
                    "bs4", "duckduckgo_search", "readability", "html2text"
                ]
            )