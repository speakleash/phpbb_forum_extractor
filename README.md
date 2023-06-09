# phpbb_forum_extractor

Version 1.0 - will only work for forums with the following pages url format:  
'.php?f=1&t=10&start=10'

Before starting the script set those params:  
domain = "forum_name" - the name of the package and url files  
base_url = "https://example-forum-base-url.com" - main page of the forum  
forum_skip = 25 - whats a step for forum pagination  
topic_skip = 10 - whats a step for topic pagination  
MIN_TEXT_LEN = 300 - whats a minimum text lenght (letters) that will be downloaded
