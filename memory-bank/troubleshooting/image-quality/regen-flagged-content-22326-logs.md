Run python -m src.regen_content
2026-02-23 21:39:50,057 INFO googleapiclient.discovery_cache: file_cache is only supported with oauth2client<4.0.0
2026-02-23 21:39:50,225 INFO src.apis.sheets_api: Google Sheets API initialized for sheet: ***
2026-02-23 21:39:50,262 INFO src.apis.image_gen: Image generation initialized: provider=openai
2026-02-23 21:39:50,384 INFO src.apis.gcs_api: GCS API initialized (bucket=slated-pipeline-pins, project=pinterest-pipeline-488017)
2026-02-23 21:39:50,425 INFO googleapiclient.discovery_cache: file_cache is only supported with oauth2client<4.0.0
2026-02-23 21:39:50,427 INFO src.apis.drive_api: Google Drive API initialized
2026-02-23 21:39:51,008 INFO src.apis.sheets_api: Found 21 regen requests in Content Queue.
2026-02-23 21:39:51,008 INFO __main__: Processing 21 regen requests
2026-02-23 21:39:51,009 INFO __main__: Regenerating regen_image for W9-P03 (type=blog, feedback='this is a picture of vegetables, not a picture of mac and cheese WITH vegetables')
2026-02-23 21:39:51,009 WARNING __main__: Blog regen not supported for W9-P03, resetting to pending_review
2026-02-23 21:39:51,397 INFO src.apis.sheets_api: Updated Content Queue row 4 (3 cells).
2026-02-23 21:39:51,397 INFO __main__: Regenerating regen_image for W9-P04 (type=blog, feedback='there is no picture here. what is supposed to go in this spot?')
2026-02-23 21:39:51,397 WARNING __main__: Blog regen not supported for W9-P04, resetting to pending_review
2026-02-23 21:39:51,579 INFO src.apis.sheets_api: Updated Content Queue row 5 (3 cells).
2026-02-23 21:39:51,579 INFO __main__: Regenerating regen_image for W9-P06 (type=blog, feedback='this picture has noodles, the recipe is just salmon teriyaki.')
2026-02-23 21:39:51,579 WARNING __main__: Blog regen not supported for W9-P06, resetting to pending_review
2026-02-23 21:39:52,423 INFO src.apis.sheets_api: Updated Content Queue row 7 (3 cells).
2026-02-23 21:39:52,423 INFO __main__: Regenerating regen_image for W9-P08 (type=blog, feedback='there is no picture')
2026-02-23 21:39:52,423 WARNING __main__: Blog regen not supported for W9-P08, resetting to pending_review
2026-02-23 21:39:52,759 INFO src.apis.sheets_api: Updated Content Queue row 9 (3 cells).
2026-02-23 21:39:52,759 INFO __main__: Regenerating regen_image for W9-P09 (type=blog, feedback='this picture has nothing to do with the blog post')
2026-02-23 21:39:52,759 WARNING __main__: Blog regen not supported for W9-P09, resetting to pending_review
2026-02-23 21:39:53,117 INFO src.apis.sheets_api: Updated Content Queue row 10 (3 cells).
2026-02-23 21:39:53,117 INFO __main__: Regenerating regen_image for W9-P10 (type=blog, feedback='this is a picture of meatballs in tomato sauce. the recipe calls for meatball bo')
2026-02-23 21:39:53,117 WARNING __main__: Blog regen not supported for W9-P10, resetting to pending_review
2026-02-23 21:39:53,447 INFO src.apis.sheets_api: Updated Content Queue row 11 (3 cells).
2026-02-23 21:39:53,447 INFO __main__: Regenerating regen_image for W9-02 (type=pin, feedback='this is chicken with oranges, the recipe talks about lemon herb chicken. this ha')
2026-02-23 21:39:53,447 INFO __main__: Regenerating image for W9-02
2026-02-23 21:39:53,448 INFO src.apis.claude_api: Generating stock image prompt for: unknown
2026-02-23 21:40:00,925 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:40:00,950 INFO src.apis.claude_api: Claude API response: model=claude-sonnet-4-20250514 input_tokens=2242 output_tokens=366 cost=$0.0122 (session total: input=2242 output=366 cost=$0.0122)
2026-02-23 21:40:00,950 INFO src.generate_pin_content: Stock search query for W9-02: 'overhead lemon herb chicken vegetables one pan'
2026-02-23 21:40:00,950 INFO src.apis.image_stock: Searching Unsplash: 'overhead lemon herb chicken vegetables one pan' (orientation=portrait, count=10)
2026-02-23 21:40:01,556 INFO src.apis.image_stock: Unsplash returned 10 results for 'overhead lemon herb chicken vegetables one pan'.
2026-02-23 21:40:01,557 INFO src.apis.image_stock: Searching Pexels: 'overhead lemon herb chicken vegetables one pan' (orientation=portrait, count=10)
2026-02-23 21:40:02,076 INFO src.apis.image_stock: Pexels returned 10 results for 'overhead lemon herb chicken vegetables one pan'.
2026-02-23 21:40:02,077 INFO src.apis.image_stock: Stock photo search for 'overhead lemon herb chicken vegetables one pan': 20 total candidates.
2026-02-23 21:40:02,693 INFO src.apis.claude_api: Ranking 5 stock candidates for pin W9-02 (template: recipe-pin)
2026-02-23 21:40:06,141 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:40:06,142 INFO src.apis.claude_api: Claude API response: model=claude-haiku-4-5-20251001 input_tokens=1431 output_tokens=309 cost=$0.0024 (session total: input=3673 output=675 cost=$0.0146)
2026-02-23 21:40:06,142 INFO src.apis.claude_api: Stock ranking complete. Top score: 8.0 (Excellent match — lemon herb chicken with fresh vegetables o), lowest: 1.5
2026-02-23 21:40:06,142 INFO src.apis.image_stock: Downloading image from unsplash: https://images.unsplash.com/photo-1609517405102-8e258999ef48?crop=entropy&cs=srg
2026-02-23 21:40:07,001 INFO src.apis.image_stock: Image downloaded: unsplash:-wMxr1Ginpo (390864 bytes) -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-02-hero.jpg
2026-02-23 21:40:07,002 INFO src.generate_pin_content: Downloaded stock image for W9-02: unsplash:unsplash:-wMxr1Ginpo (score: 8.0)
2026-02-23 21:40:07,002 INFO src.pin_assembler: Rendering recipe-pin variant A -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-02.png
2026-02-23 21:40:09,842 INFO src.pin_assembler: Converted to JPEG: 263312 bytes (was 1514032 bytes PNG)
2026-02-23 21:40:09,842 INFO src.pin_assembler: Pin rendered successfully: /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-02.png (263312 bytes)
2026-02-23 21:40:10,174 INFO __main__: Uploaded regen pin W9-02 to GCS: https://storage.googleapis.com/slated-pipeline-pins/W9-02.png
2026-02-23 21:40:10,533 INFO src.apis.sheets_api: Updated Content Queue row 13 (4 cells).
2026-02-23 21:40:10,533 INFO __main__: Regenerating regen for W9-09 (type=pin, feedback='this is a picture of vegetables not a picture of macroni and cheese with vegetab')
2026-02-23 21:40:10,533 INFO __main__: Regenerating copy for W9-09
2026-02-23 21:40:10,533 INFO src.apis.claude_api: Generating pin copy batch 1-1 of 1...
2026-02-23 21:40:17,254 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:40:17,255 INFO src.apis.claude_api: Claude API response: model=claude-sonnet-4-20250514 input_tokens=4769 output_tokens=261 cost=$0.0182 (session total: input=8442 output=936 cost=$0.0328)
2026-02-23 21:40:17,256 INFO __main__: Copy regenerated for W9-09: 'Mac and Cheese with Secret Veggies — Kid Friendly Dinners Th'
2026-02-23 21:40:17,256 INFO __main__: Regenerating image for W9-09
2026-02-23 21:40:17,256 INFO src.apis.claude_api: Generating stock image prompt for: unknown
2026-02-23 21:40:25,128 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:40:25,129 INFO src.apis.claude_api: Claude API response: model=claude-sonnet-4-20250514 input_tokens=2265 output_tokens=378 cost=$0.0125 (session total: input=10707 output=1314 cost=$0.0453)
2026-02-23 21:40:25,129 INFO src.generate_pin_content: Stock search query for W9-09: 'overhead mac and cheese vegetables hidden kids'
2026-02-23 21:40:25,129 INFO src.apis.image_stock: Searching Unsplash: 'overhead mac and cheese vegetables hidden kids' (orientation=portrait, count=10)
2026-02-23 21:40:25,688 INFO src.apis.image_stock: Unsplash returned 10 results for 'overhead mac and cheese vegetables hidden kids'.
2026-02-23 21:40:25,689 INFO src.apis.image_stock: Searching Pexels: 'overhead mac and cheese vegetables hidden kids' (orientation=portrait, count=10)
2026-02-23 21:40:26,078 INFO src.apis.image_stock: Pexels returned 10 results for 'overhead mac and cheese vegetables hidden kids'.
2026-02-23 21:40:26,079 INFO src.apis.image_stock: Stock photo search for 'overhead mac and cheese vegetables hidden kids': 20 total candidates.
2026-02-23 21:40:26,593 INFO src.apis.claude_api: Ranking 5 stock candidates for pin W9-09 (template: recipe-pin)
2026-02-23 21:40:31,817 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:40:31,818 INFO src.apis.claude_api: Claude API response: model=claude-haiku-4-5-20251001 input_tokens=1462 output_tokens=413 cost=$0.0028 (session total: input=12169 output=1727 cost=$0.0481)
2026-02-23 21:40:31,818 INFO src.apis.claude_api: Stock ranking complete. Top score: 9.0 (Perfect match for hidden veggie recipe pin. Overhead flat-la), lowest: 1.0
2026-02-23 21:40:31,818 INFO src.apis.image_stock: Downloading image from unsplash: https://images.unsplash.com/photo-1550497507-634bd6d81ecd?crop=entropy&cs=srgb&f
2026-02-23 21:40:32,539 INFO src.apis.image_stock: Image downloaded: unsplash:eS07Cany2g4 (313968 bytes) -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-09-hero.jpg
2026-02-23 21:40:32,540 INFO src.generate_pin_content: Downloaded stock image for W9-09: unsplash:unsplash:eS07Cany2g4 (score: 9.0)
2026-02-23 21:40:32,541 INFO src.pin_assembler: Rendering recipe-pin variant A -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-09.png
2026-02-23 21:40:35,090 INFO src.pin_assembler: Converted to JPEG: 293362 bytes (was 1627895 bytes PNG)
2026-02-23 21:40:35,091 INFO src.pin_assembler: Pin rendered successfully: /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-09.png (293362 bytes)
2026-02-23 21:40:35,308 INFO __main__: Uploaded regen pin W9-09 to GCS: https://storage.googleapis.com/slated-pipeline-pins/W9-09.png
2026-02-23 21:40:35,675 INFO src.apis.sheets_api: Updated Content Queue row 20 (6 cells).
2026-02-23 21:40:35,675 INFO __main__: Regenerating regen_image for W9-12 (type=pin, feedback='this picture has noodles. this should be a bowl with teriyaki salmon, white rice')
2026-02-23 21:40:35,675 INFO __main__: Regenerating image for W9-12
2026-02-23 21:40:35,675 INFO src.apis.claude_api: Generating stock image prompt for: unknown
2026-02-23 21:40:41,494 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:40:41,495 INFO src.apis.claude_api: Claude API response: model=claude-sonnet-4-20250514 input_tokens=2245 output_tokens=318 cost=$0.0115 (session total: input=14414 output=2045 cost=$0.0596)
2026-02-23 21:40:41,495 INFO src.generate_pin_content: Stock search query for W9-12: 'teriyaki salmon bowl rice vegetables overhead'
2026-02-23 21:40:41,495 INFO src.apis.image_stock: Searching Unsplash: 'teriyaki salmon bowl rice vegetables overhead' (orientation=portrait, count=10)
2026-02-23 21:40:41,768 INFO src.apis.image_stock: Unsplash returned 0 results for 'teriyaki salmon bowl rice vegetables overhead'.
2026-02-23 21:40:41,769 INFO src.apis.image_stock: Searching Pexels: 'teriyaki salmon bowl rice vegetables overhead' (orientation=portrait, count=10)
2026-02-23 21:40:42,087 INFO src.apis.image_stock: Pexels returned 10 results for 'teriyaki salmon bowl rice vegetables overhead'.
2026-02-23 21:40:42,088 INFO src.apis.image_stock: Stock photo search for 'teriyaki salmon bowl rice vegetables overhead': 10 total candidates.
2026-02-23 21:40:42,959 INFO src.apis.claude_api: Ranking 5 stock candidates for pin W9-12 (template: recipe-pin)
2026-02-23 21:40:47,119 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:40:47,120 INFO src.apis.claude_api: Claude API response: model=claude-haiku-4-5-20251001 input_tokens=1419 output_tokens=324 cost=$0.0024 (session total: input=15833 output=2369 cost=$0.0620)
2026-02-23 21:40:47,120 INFO src.apis.claude_api: Stock ranking complete. Top score: 7.5 (Good overhead composition with warm natural lighting. Bowl c), lowest: 2.0
2026-02-23 21:40:47,120 INFO src.apis.image_stock: Downloading image from pexels: https://images.pexels.com/photos/4828099/pexels-photo-4828099.jpeg
2026-02-23 21:40:47,225 INFO src.apis.image_stock: Image downloaded: pexels:4828099 (257486 bytes) -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-12-hero.jpg
2026-02-23 21:40:47,225 INFO src.generate_pin_content: Downloaded stock image for W9-12: pexels:pexels:4828099 (score: 7.5)
2026-02-23 21:40:47,226 INFO src.pin_assembler: Rendering recipe-pin variant A -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-12.png
2026-02-23 21:40:49,481 INFO src.pin_assembler: Converted to JPEG: 149179 bytes (was 739523 bytes PNG)
2026-02-23 21:40:49,481 INFO src.pin_assembler: Pin rendered successfully: /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-12.png (149179 bytes)
2026-02-23 21:40:49,680 INFO __main__: Uploaded regen pin W9-12 to GCS: https://storage.googleapis.com/slated-pipeline-pins/W9-12.png
2026-02-23 21:40:49,887 INFO src.apis.sheets_api: Updated Content Queue row 23 (4 cells).
2026-02-23 21:40:49,887 INFO __main__: Regenerating regen_image for W9-16 (type=pin, feedback='this is turkey meatballs in tomato sauce not Turkey meatballs over rice and vegg')
2026-02-23 21:40:49,887 INFO __main__: Regenerating image for W9-16
2026-02-23 21:40:49,888 INFO src.apis.claude_api: Generating stock image prompt for: unknown
2026-02-23 21:40:56,052 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:40:56,053 INFO src.apis.claude_api: Claude API response: model=claude-sonnet-4-20250514 input_tokens=2239 output_tokens=340 cost=$0.0118 (session total: input=18072 output=2709 cost=$0.0739)
2026-02-23 21:40:56,053 INFO src.generate_pin_content: Stock search query for W9-16: 'turkey meatballs rice bowl vegetables overhead'
2026-02-23 21:40:56,053 INFO src.apis.image_stock: Searching Unsplash: 'turkey meatballs rice bowl vegetables overhead' (orientation=portrait, count=10)
2026-02-23 21:40:56,559 INFO src.apis.image_stock: Unsplash returned 10 results for 'turkey meatballs rice bowl vegetables overhead'.
2026-02-23 21:40:56,560 INFO src.apis.image_stock: Searching Pexels: 'turkey meatballs rice bowl vegetables overhead' (orientation=portrait, count=10)
2026-02-23 21:40:56,898 INFO src.apis.image_stock: Pexels returned 10 results for 'turkey meatballs rice bowl vegetables overhead'.
2026-02-23 21:40:56,898 INFO src.apis.image_stock: Stock photo search for 'turkey meatballs rice bowl vegetables overhead': 20 total candidates.
2026-02-23 21:40:57,654 INFO src.apis.claude_api: Ranking 5 stock candidates for pin W9-16 (template: recipe-pin)
2026-02-23 21:41:01,248 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:41:01,249 INFO src.apis.claude_api: Claude API response: model=claude-haiku-4-5-20251001 input_tokens=1516 output_tokens=326 cost=$0.0025 (session total: input=19588 output=3035 cost=$0.0764)
2026-02-23 21:41:01,249 INFO src.apis.claude_api: Stock ranking complete. Top score: 7.5 (Correct subject — turkey meatballs in sauce with garnish. Wa), lowest: 2.0
2026-02-23 21:41:01,249 INFO src.apis.image_stock: Downloading image from unsplash: https://images.unsplash.com/photo-1587217518657-fa94faff4e7e?crop=entropy&cs=srg
2026-02-23 21:41:01,769 INFO src.apis.image_stock: Image downloaded: unsplash:q9gYYnlTi5U (359485 bytes) -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-16-hero.jpg
2026-02-23 21:41:01,770 INFO src.generate_pin_content: Downloaded stock image for W9-16: unsplash:unsplash:q9gYYnlTi5U (score: 7.5)
2026-02-23 21:41:01,770 INFO src.pin_assembler: Rendering recipe-pin variant A -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-16.png
2026-02-23 21:41:04,493 INFO src.pin_assembler: Converted to JPEG: 280052 bytes (was 1511600 bytes PNG)
2026-02-23 21:41:04,494 INFO src.pin_assembler: Pin rendered successfully: /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-16.png (280052 bytes)
2026-02-23 21:41:04,667 INFO __main__: Uploaded regen pin W9-16 to GCS: https://storage.googleapis.com/slated-pipeline-pins/W9-16.png
2026-02-23 21:41:05,081 INFO src.apis.sheets_api: Updated Content Queue row 27 (4 cells).
2026-02-23 21:41:05,081 INFO __main__: Regenerating regen_image for W9-17 (type=pin, feedback='i have no idea what this is a picture of but it is not chicken and rice in one p')
2026-02-23 21:41:05,081 INFO __main__: Regenerating image for W9-17
2026-02-23 21:41:05,082 INFO src.apis.claude_api: Generating stock image prompt for: unknown
2026-02-23 21:41:12,031 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:41:12,032 INFO src.apis.claude_api: Claude API response: model=claude-sonnet-4-20250514 input_tokens=2235 output_tokens=340 cost=$0.0118 (session total: input=21823 output=3375 cost=$0.0882)
2026-02-23 21:41:12,032 INFO src.generate_pin_content: Stock search query for W9-17: 'chicken rice skillet one pan overhead'
2026-02-23 21:41:12,032 INFO src.apis.image_stock: Searching Unsplash: 'chicken rice skillet one pan overhead' (orientation=portrait, count=10)
2026-02-23 21:41:12,296 INFO src.apis.image_stock: Unsplash returned 0 results for 'chicken rice skillet one pan overhead'.
2026-02-23 21:41:12,297 INFO src.apis.image_stock: Searching Pexels: 'chicken rice skillet one pan overhead' (orientation=portrait, count=10)
2026-02-23 21:41:12,665 INFO src.apis.image_stock: Pexels returned 10 results for 'chicken rice skillet one pan overhead'.
2026-02-23 21:41:12,666 INFO src.apis.image_stock: Stock photo search for 'chicken rice skillet one pan overhead': 10 total candidates.
2026-02-23 21:41:14,955 INFO src.apis.claude_api: Ranking 5 stock candidates for pin W9-17 (template: recipe-pin)
2026-02-23 21:41:18,751 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:41:18,752 INFO src.apis.claude_api: Claude API response: model=claude-haiku-4-5-20251001 input_tokens=1409 output_tokens=286 cost=$0.0023 (session total: input=23232 output=3661 cost=$0.0905)
2026-02-23 21:41:18,752 INFO src.apis.claude_api: Stock ranking complete. Top score: 9.0 (Perfect match for spring chicken skillet. Overhead compositi), lowest: 2.0
2026-02-23 21:41:18,752 INFO src.apis.image_stock: Downloading image from pexels: https://images.pexels.com/photos/25884476/pexels-photo-25884476.jpeg
2026-02-23 21:41:18,881 INFO src.apis.image_stock: Image downloaded: pexels:25884476 (2236037 bytes) -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-17-hero.jpg
2026-02-23 21:41:18,882 INFO src.generate_pin_content: Downloaded stock image for W9-17: pexels:pexels:25884476 (score: 9.0)
2026-02-23 21:41:18,882 INFO src.pin_assembler: Rendering recipe-pin variant A -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-17.png
2026-02-23 21:41:22,192 INFO src.pin_assembler: Converted to JPEG: 271965 bytes (was 1591206 bytes PNG)
2026-02-23 21:41:22,192 INFO src.pin_assembler: Pin rendered successfully: /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-17.png (271965 bytes)
2026-02-23 21:41:22,379 INFO __main__: Uploaded regen pin W9-17 to GCS: https://storage.googleapis.com/slated-pipeline-pins/W9-17.png
2026-02-23 21:41:22,634 INFO src.apis.sheets_api: Updated Content Queue row 28 (4 cells).
2026-02-23 21:41:22,634 INFO __main__: Regenerating regen_image for W9-18 (type=pin, feedback='this is a picture of broccoli, not a picture of beef and broccoli stir-fry')
2026-02-23 21:41:22,634 INFO __main__: Regenerating image for W9-18
2026-02-23 21:41:22,635 INFO src.apis.claude_api: Generating stock image prompt for: unknown
2026-02-23 21:41:28,932 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:41:28,936 INFO src.apis.claude_api: Claude API response: model=claude-sonnet-4-20250514 input_tokens=2245 output_tokens=353 cost=$0.0120 (session total: input=25477 output=4014 cost=$0.1025)
2026-02-23 21:41:28,936 INFO src.generate_pin_content: Stock search query for W9-18: 'beef broccoli stir fry wok overhead'
2026-02-23 21:41:28,936 INFO src.apis.image_stock: Searching Unsplash: 'beef broccoli stir fry wok overhead' (orientation=portrait, count=10)
2026-02-23 21:41:29,469 INFO src.apis.image_stock: Unsplash returned 10 results for 'beef broccoli stir fry wok overhead'.
2026-02-23 21:41:29,470 INFO src.apis.image_stock: Searching Pexels: 'beef broccoli stir fry wok overhead' (orientation=portrait, count=10)
2026-02-23 21:41:29,826 INFO src.apis.image_stock: Pexels returned 10 results for 'beef broccoli stir fry wok overhead'.
2026-02-23 21:41:29,826 INFO src.apis.image_stock: Stock photo search for 'beef broccoli stir fry wok overhead': 20 total candidates.
2026-02-23 21:41:29,991 INFO src.apis.claude_api: Ranking 5 stock candidates for pin W9-18 (template: recipe-pin)
2026-02-23 21:41:33,982 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:41:33,983 INFO src.apis.claude_api: Claude API response: model=claude-haiku-4-5-20251001 input_tokens=1460 output_tokens=336 cost=$0.0025 (session total: input=26937 output=4350 cost=$0.1050)
2026-02-23 21:41:33,983 INFO src.apis.claude_api: Stock ranking complete. Top score: 7.5 (Shows a stir-fry cooking in a pan on stovetop with visible v), lowest: 2.0
2026-02-23 21:41:33,983 INFO src.apis.image_stock: Downloading image from unsplash: https://images.unsplash.com/photo-1585863481734-ff56631d441c?crop=entropy&cs=srg
2026-02-23 21:41:34,626 INFO src.apis.image_stock: Image downloaded: unsplash:HDSX4xPIvqo (288885 bytes) -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-18-hero.jpg
2026-02-23 21:41:34,627 INFO src.generate_pin_content: Downloaded stock image for W9-18: unsplash:unsplash:HDSX4xPIvqo (score: 7.5)
2026-02-23 21:41:34,627 INFO src.pin_assembler: Rendering recipe-pin variant A -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-18.png
2026-02-23 21:41:37,176 INFO src.pin_assembler: Converted to JPEG: 250871 bytes (was 1314581 bytes PNG)
2026-02-23 21:41:37,176 INFO src.pin_assembler: Pin rendered successfully: /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-18.png (250871 bytes)
2026-02-23 21:41:37,353 INFO __main__: Uploaded regen pin W9-18 to GCS: https://storage.googleapis.com/slated-pipeline-pins/W9-18.png
2026-02-23 21:41:37,574 INFO src.apis.sheets_api: Updated Content Queue row 29 (4 cells).
2026-02-23 21:41:37,574 INFO __main__: Regenerating regen for W9-19 (type=pin, feedback='this should be a stock image not a template')
2026-02-23 21:41:37,574 INFO __main__: Regenerating copy for W9-19
2026-02-23 21:41:37,599 INFO src.apis.claude_api: Generating pin copy batch 1-1 of 1...
2026-02-23 21:41:43,780 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:41:43,781 INFO src.apis.claude_api: Claude API response: model=claude-sonnet-4-20250514 input_tokens=4690 output_tokens=250 cost=$0.0178 (session total: input=31627 output=4600 cost=$0.1228)
2026-02-23 21:41:43,781 INFO __main__: Copy regenerated for W9-19: 'Hidden Veggie Recipes Kids Actually Eat — 12 Sneaky Dinner I'
2026-02-23 21:41:43,781 INFO __main__: Regenerating image for W9-19
2026-02-23 21:41:43,781 INFO src.apis.claude_api: Generating stock image prompt for: unknown
2026-02-23 21:41:50,958 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:41:50,958 INFO src.apis.claude_api: Claude API response: model=claude-sonnet-4-20250514 input_tokens=2227 output_tokens=343 cost=$0.0118 (session total: input=33854 output=4943 cost=$0.1346)
2026-02-23 21:41:50,958 INFO src.generate_pin_content: Stock search query for W9-19: 'kids eating vegetables dinner plate colorful'
2026-02-23 21:41:50,959 INFO src.apis.image_stock: Searching Unsplash: 'kids eating vegetables dinner plate colorful' (orientation=portrait, count=10)
2026-02-23 21:41:51,502 INFO src.apis.image_stock: Unsplash returned 10 results for 'kids eating vegetables dinner plate colorful'.
2026-02-23 21:41:51,503 INFO src.apis.image_stock: Searching Pexels: 'kids eating vegetables dinner plate colorful' (orientation=portrait, count=10)
2026-02-23 21:41:52,015 INFO src.apis.image_stock: Pexels returned 10 results for 'kids eating vegetables dinner plate colorful'.
2026-02-23 21:41:52,016 INFO src.apis.image_stock: Stock photo search for 'kids eating vegetables dinner plate colorful': 20 total candidates.
2026-02-23 21:41:52,627 INFO src.apis.claude_api: Ranking 5 stock candidates for pin W9-19 (template: listicle-pin)
2026-02-23 21:41:57,861 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:41:57,864 INFO src.apis.claude_api: Claude API response: model=claude-haiku-4-5-20251001 input_tokens=1409 output_tokens=404 cost=$0.0027 (session total: input=35263 output=5347 cost=$0.1374)
2026-02-23 21:41:57,864 INFO src.apis.claude_api: Stock ranking complete. Top score: 8.5 (Excellent overhead flat-lay of colorful veggie bowl with cle), lowest: 2.0
2026-02-23 21:41:57,864 INFO src.apis.image_stock: Downloading image from unsplash: https://images.unsplash.com/photo-1741231954134-960dae8d9ffe?crop=entropy&cs=srg
2026-02-23 21:41:59,254 INFO src.apis.image_stock: Image downloaded: unsplash:31st2dvwGUs (237917 bytes) -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-19-hero.jpg
2026-02-23 21:41:59,255 INFO src.generate_pin_content: Downloaded stock image for W9-19: unsplash:unsplash:31st2dvwGUs (score: 8.5)
2026-02-23 21:41:59,255 INFO src.pin_assembler: Rendering listicle-pin variant A -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-19.png
2026-02-23 21:42:04,590 INFO src.pin_assembler: Converted to JPEG: 171883 bytes (was 1087516 bytes PNG)
2026-02-23 21:42:04,590 INFO src.pin_assembler: Pin rendered successfully: /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-19.png (171883 bytes)
2026-02-23 21:42:04,763 INFO __main__: Uploaded regen pin W9-19 to GCS: https://storage.googleapis.com/slated-pipeline-pins/W9-19.png
2026-02-23 21:42:04,992 INFO src.apis.sheets_api: Updated Content Queue row 30 (6 cells).
2026-02-23 21:42:04,992 INFO __main__: Regenerating regen_image for W9-20 (type=pin, feedback='this should be a stock image not a template')
2026-02-23 21:42:04,992 INFO __main__: Regenerating image for W9-20
2026-02-23 21:42:04,993 INFO src.apis.claude_api: Generating stock image prompt for: unknown
2026-02-23 21:42:12,194 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:42:12,195 INFO src.apis.claude_api: Claude API response: model=claude-sonnet-4-20250514 input_tokens=2223 output_tokens=314 cost=$0.0114 (session total: input=37486 output=5661 cost=$0.1488)
2026-02-23 21:42:12,195 INFO src.generate_pin_content: Stock search query for W9-20: 'family dinner table overhead multiple plates'
2026-02-23 21:42:12,195 INFO src.apis.image_stock: Searching Unsplash: 'family dinner table overhead multiple plates' (orientation=portrait, count=10)
2026-02-23 21:42:12,523 INFO src.apis.image_stock: Unsplash returned 10 results for 'family dinner table overhead multiple plates'.
2026-02-23 21:42:12,524 INFO src.apis.image_stock: Searching Pexels: 'family dinner table overhead multiple plates' (orientation=portrait, count=10)
2026-02-23 21:42:12,922 INFO src.apis.image_stock: Pexels returned 10 results for 'family dinner table overhead multiple plates'.
2026-02-23 21:42:12,923 INFO src.apis.image_stock: Stock photo search for 'family dinner table overhead multiple plates': 20 total candidates.
2026-02-23 21:42:14,525 INFO src.apis.claude_api: Ranking 5 stock candidates for pin W9-20 (template: tip-pin)
2026-02-23 21:42:18,337 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:42:18,338 INFO src.apis.claude_api: Claude API response: model=claude-haiku-4-5-20251001 input_tokens=1412 output_tokens=310 cost=$0.0024 (session total: input=38898 output=5971 cost=$0.1511)
2026-02-23 21:42:18,338 INFO src.apis.claude_api: Stock ranking complete. Top score: 8.0 (Elegant table setting with warm lighting, orange accents, an), lowest: 2.0
2026-02-23 21:42:18,338 INFO src.apis.image_stock: Downloading image from unsplash: https://images.unsplash.com/photo-1766931586319-8f51b17bb80a?crop=entropy&cs=srg
2026-02-23 21:42:19,629 INFO src.apis.image_stock: Image downloaded: unsplash:p-aFwK7toYo (252497 bytes) -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-20-hero.jpg
2026-02-23 21:42:19,630 INFO src.generate_pin_content: Downloaded stock image for W9-20: unsplash:unsplash:p-aFwK7toYo (score: 8.0)
2026-02-23 21:42:19,631 INFO src.pin_assembler: Rendering tip-pin variant A -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-20.png
2026-02-23 21:42:25,334 INFO src.pin_assembler: Converted to JPEG: 152266 bytes (was 1293180 bytes PNG)
2026-02-23 21:42:25,334 INFO src.pin_assembler: Pin rendered successfully: /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-20.png (152266 bytes)
2026-02-23 21:42:25,510 INFO __main__: Uploaded regen pin W9-20 to GCS: https://storage.googleapis.com/slated-pipeline-pins/W9-20.png
2026-02-23 21:42:25,895 INFO src.apis.sheets_api: Updated Content Queue row 31 (4 cells).
2026-02-23 21:42:25,895 INFO __main__: Regenerating regen_image for W9-21 (type=pin, feedback='this should be a stock image not a template')
2026-02-23 21:42:25,895 INFO __main__: Regenerating image for W9-21
2026-02-23 21:42:25,896 INFO src.apis.claude_api: Generating stock image prompt for: unknown
2026-02-23 21:42:32,034 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:42:32,035 INFO src.apis.claude_api: Claude API response: model=claude-sonnet-4-20250514 input_tokens=2225 output_tokens=333 cost=$0.0117 (session total: input=41123 output=6304 cost=$0.1628)
2026-02-23 21:42:32,035 INFO src.generate_pin_content: Stock search query for W9-21: 'one pan chicken vegetables skillet overhead'
2026-02-23 21:42:32,035 INFO src.apis.image_stock: Searching Unsplash: 'one pan chicken vegetables skillet overhead' (orientation=portrait, count=10)
2026-02-23 21:42:32,702 INFO src.apis.image_stock: Unsplash returned 10 results for 'one pan chicken vegetables skillet overhead'.
2026-02-23 21:42:32,703 INFO src.apis.image_stock: Searching Pexels: 'one pan chicken vegetables skillet overhead' (orientation=portrait, count=10)
2026-02-23 21:42:33,122 INFO src.apis.image_stock: Pexels returned 10 results for 'one pan chicken vegetables skillet overhead'.
2026-02-23 21:42:33,123 INFO src.apis.image_stock: Stock photo search for 'one pan chicken vegetables skillet overhead': 20 total candidates.
2026-02-23 21:42:33,306 INFO src.apis.claude_api: Ranking 5 stock candidates for pin W9-21 (template: tip-pin)
2026-02-23 21:42:37,928 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:42:37,928 INFO src.apis.claude_api: Claude API response: model=claude-haiku-4-5-20251001 input_tokens=1410 output_tokens=360 cost=$0.0026 (session total: input=42533 output=6664 cost=$0.1654)
2026-02-23 21:42:37,928 INFO src.apis.claude_api: Stock ranking complete. Top score: 8.5 (Excellent match for one-pan spring dinner. Overhead composit), lowest: 4.0
2026-02-23 21:42:37,929 INFO src.apis.image_stock: Downloading image from unsplash: https://images.unsplash.com/photo-1698843813577-db28459556b0?crop=entropy&cs=srg
2026-02-23 21:42:37,978 INFO src.apis.image_stock: Image downloaded: unsplash:H-D-0UOgzMc (190771 bytes) -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-21-hero.jpg
2026-02-23 21:42:37,979 INFO src.generate_pin_content: Downloaded stock image for W9-21: unsplash:unsplash:H-D-0UOgzMc (score: 8.5)
2026-02-23 21:42:37,979 INFO src.pin_assembler: Rendering tip-pin variant A -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-21.png
2026-02-23 21:42:42,255 INFO src.pin_assembler: Converted to JPEG: 148003 bytes (was 952815 bytes PNG)
2026-02-23 21:42:42,255 INFO src.pin_assembler: Pin rendered successfully: /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-21.png (148003 bytes)
2026-02-23 21:42:42,444 INFO __main__: Uploaded regen pin W9-21 to GCS: https://storage.googleapis.com/slated-pipeline-pins/W9-21.png
2026-02-23 21:42:42,663 INFO src.apis.sheets_api: Updated Content Queue row 32 (4 cells).
2026-02-23 21:42:42,663 INFO __main__: Regenerating regen_image for W9-22 (type=pin, feedback='this should be a stock image not a template')
2026-02-23 21:42:42,663 INFO __main__: Regenerating image for W9-22
2026-02-23 21:42:42,663 INFO src.apis.claude_api: Generating stock image prompt for: unknown
2026-02-23 21:42:49,593 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:42:49,599 INFO src.apis.claude_api: Claude API response: model=claude-sonnet-4-20250514 input_tokens=2225 output_tokens=326 cost=$0.0116 (session total: input=44758 output=6990 cost=$0.1769)
2026-02-23 21:42:49,599 INFO src.generate_pin_content: Stock search query for W9-22: 'quick dinner plate overhead 15 minutes'
2026-02-23 21:42:49,599 INFO src.apis.image_stock: Searching Unsplash: 'quick dinner plate overhead 15 minutes' (orientation=portrait, count=10)
2026-02-23 21:42:50,135 INFO src.apis.image_stock: Unsplash returned 10 results for 'quick dinner plate overhead 15 minutes'.
2026-02-23 21:42:50,136 INFO src.apis.image_stock: Searching Pexels: 'quick dinner plate overhead 15 minutes' (orientation=portrait, count=10)
2026-02-23 21:42:50,556 INFO src.apis.image_stock: Pexels returned 10 results for 'quick dinner plate overhead 15 minutes'.
2026-02-23 21:42:50,557 INFO src.apis.image_stock: Stock photo search for 'quick dinner plate overhead 15 minutes': 20 total candidates.
2026-02-23 21:42:51,071 INFO src.apis.claude_api: Ranking 5 stock candidates for pin W9-22 (template: listicle-pin)
2026-02-23 21:42:56,266 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:42:56,266 INFO src.apis.claude_api: Claude API response: model=claude-haiku-4-5-20251001 input_tokens=1408 output_tokens=369 cost=$0.0026 (session total: input=46166 output=7359 cost=$0.1795)
2026-02-23 21:42:56,266 INFO src.apis.claude_api: Stock ranking complete. Top score: 8.5 (Excellent overhead flat-lay composition of a quick skillet m), lowest: 4.0
2026-02-23 21:42:56,266 INFO src.apis.image_stock: Downloading image from unsplash: https://images.unsplash.com/photo-1611962424660-201a4af8f496?crop=entropy&cs=srg
2026-02-23 21:42:56,800 INFO src.apis.image_stock: Image downloaded: unsplash:0CFIC4hgZ8g (173234 bytes) -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-22-hero.jpg
2026-02-23 21:42:56,801 INFO src.generate_pin_content: Downloaded stock image for W9-22: unsplash:unsplash:0CFIC4hgZ8g (score: 8.5)
2026-02-23 21:42:56,801 INFO src.pin_assembler: Rendering listicle-pin variant A -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-22.png
2026-02-23 21:42:59,189 INFO src.pin_assembler: Converted to JPEG: 115808 bytes (was 740326 bytes PNG)
2026-02-23 21:42:59,189 INFO src.pin_assembler: Pin rendered successfully: /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-22.png (115808 bytes)
2026-02-23 21:42:59,340 INFO __main__: Uploaded regen pin W9-22 to GCS: https://storage.googleapis.com/slated-pipeline-pins/W9-22.png
2026-02-23 21:42:59,750 INFO src.apis.sheets_api: Updated Content Queue row 33 (4 cells).
2026-02-23 21:42:59,750 INFO __main__: Regenerating regen_image for W9-23 (type=pin, feedback='this should be a stock image not a template')
2026-02-23 21:42:59,750 INFO __main__: Regenerating image for W9-23
2026-02-23 21:42:59,750 INFO src.apis.claude_api: Generating stock image prompt for: unknown
2026-02-23 21:43:05,667 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:43:05,668 INFO src.apis.claude_api: Claude API response: model=claude-sonnet-4-20250514 input_tokens=2221 output_tokens=319 cost=$0.0114 (session total: input=48387 output=7678 cost=$0.1910)
2026-02-23 21:43:05,668 INFO src.generate_pin_content: Stock search query for W9-23: 'overhead creamy pasta dinner family plate'
2026-02-23 21:43:05,668 INFO src.apis.image_stock: Searching Unsplash: 'overhead creamy pasta dinner family plate' (orientation=portrait, count=10)
2026-02-23 21:43:06,264 INFO src.apis.image_stock: Unsplash returned 10 results for 'overhead creamy pasta dinner family plate'.
2026-02-23 21:43:06,265 INFO src.apis.image_stock: Searching Pexels: 'overhead creamy pasta dinner family plate' (orientation=portrait, count=10)
2026-02-23 21:43:06,712 INFO src.apis.image_stock: Pexels returned 10 results for 'overhead creamy pasta dinner family plate'.
2026-02-23 21:43:06,712 INFO src.apis.image_stock: Stock photo search for 'overhead creamy pasta dinner family plate': 20 total candidates.
2026-02-23 21:43:06,889 INFO src.apis.claude_api: Ranking 5 stock candidates for pin W9-23 (template: listicle-pin)
2026-02-23 21:43:11,657 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:43:11,657 INFO src.apis.claude_api: Claude API response: model=claude-haiku-4-5-20251001 input_tokens=1426 output_tokens=361 cost=$0.0026 (session total: input=49813 output=8039 cost=$0.1936)
2026-02-23 21:43:11,657 INFO src.apis.claude_api: Stock ranking complete. Top score: 8.5 (Excellent match for creamy pasta recipe pin. Warm, natural l), lowest: 2.0
2026-02-23 21:43:11,658 INFO src.apis.image_stock: Downloading image from unsplash: https://images.unsplash.com/photo-1733700469234-959507e92420?crop=entropy&cs=srg
2026-02-23 21:43:11,705 INFO src.apis.image_stock: Image downloaded: unsplash:PpmLfADlCmA (225415 bytes) -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-23-hero.jpg
2026-02-23 21:43:11,705 INFO src.generate_pin_content: Downloaded stock image for W9-23: unsplash:unsplash:PpmLfADlCmA (score: 8.5)
2026-02-23 21:43:11,706 INFO src.pin_assembler: Rendering listicle-pin variant A -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-23.png
2026-02-23 21:43:17,578 INFO src.pin_assembler: Converted to JPEG: 156434 bytes (was 1120846 bytes PNG)
2026-02-23 21:43:17,578 INFO src.pin_assembler: Pin rendered successfully: /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-23.png (156434 bytes)
2026-02-23 21:43:17,756 INFO __main__: Uploaded regen pin W9-23 to GCS: https://storage.googleapis.com/slated-pipeline-pins/W9-23.png
2026-02-23 21:43:17,972 INFO src.apis.sheets_api: Updated Content Queue row 34 (4 cells).
2026-02-23 21:43:17,972 INFO __main__: Regenerating regen_image for W9-24 (type=pin, feedback='this should be a stock image not a template')
2026-02-23 21:43:17,972 INFO __main__: Regenerating image for W9-24
2026-02-23 21:43:17,972 INFO src.apis.claude_api: Generating stock image prompt for: unknown
2026-02-23 21:43:24,197 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:43:24,198 INFO src.apis.claude_api: Claude API response: model=claude-sonnet-4-20250514 input_tokens=2217 output_tokens=312 cost=$0.0113 (session total: input=52030 output=8351 cost=$0.2049)
2026-02-23 21:43:24,198 INFO src.generate_pin_content: Stock search query for W9-24: 'meal prep containers organized kitchen counter'
2026-02-23 21:43:24,198 INFO src.apis.image_stock: Searching Unsplash: 'meal prep containers organized kitchen counter' (orientation=portrait, count=10)
2026-02-23 21:43:24,491 INFO src.apis.image_stock: Unsplash returned 3 results for 'meal prep containers organized kitchen counter'.
2026-02-23 21:43:24,492 INFO src.apis.image_stock: Searching Pexels: 'meal prep containers organized kitchen counter' (orientation=portrait, count=10)
2026-02-23 21:43:24,817 INFO src.apis.image_stock: Pexels returned 10 results for 'meal prep containers organized kitchen counter'.
2026-02-23 21:43:24,818 INFO src.apis.image_stock: Stock photo search for 'meal prep containers organized kitchen counter': 13 total candidates.
2026-02-23 21:43:26,165 INFO src.apis.claude_api: Ranking 5 stock candidates for pin W9-24 (template: tip-pin)
2026-02-23 21:43:30,388 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:43:30,389 INFO src.apis.claude_api: Claude API response: model=claude-haiku-4-5-20251001 input_tokens=1405 output_tokens=329 cost=$0.0024 (session total: input=53435 output=8680 cost=$0.2073)
2026-02-23 21:43:30,389 INFO src.apis.claude_api: Stock ranking complete. Top score: 7.5 (Clear action shot of pouring grains/ingredients into a conta), lowest: 2.0
2026-02-23 21:43:30,389 INFO src.apis.image_stock: Downloading image from pexels: https://images.pexels.com/photos/8581005/pexels-photo-8581005.jpeg
2026-02-23 21:43:31,387 INFO src.apis.image_stock: Image downloaded: pexels:8581005 (1687993 bytes) -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-24-hero.jpg
2026-02-23 21:43:31,389 INFO src.generate_pin_content: Downloaded stock image for W9-24: pexels:pexels:8581005 (score: 7.5)
2026-02-23 21:43:31,390 INFO src.pin_assembler: Rendering tip-pin variant A -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-24.png
2026-02-23 21:43:37,371 INFO src.pin_assembler: Converted to JPEG: 117538 bytes (was 1018040 bytes PNG)
2026-02-23 21:43:37,372 INFO src.pin_assembler: Pin rendered successfully: /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-24.png (117538 bytes)
2026-02-23 21:43:37,540 INFO __main__: Uploaded regen pin W9-24 to GCS: https://storage.googleapis.com/slated-pipeline-pins/W9-24.png
2026-02-23 21:43:37,747 INFO src.apis.sheets_api: Updated Content Queue row 35 (4 cells).
2026-02-23 21:43:37,747 INFO __main__: Regenerating regen_image for W9-25 (type=pin, feedback='this should be a stock image not a template')
2026-02-23 21:43:37,747 INFO __main__: Regenerating image for W9-25
2026-02-23 21:43:37,748 INFO src.apis.claude_api: Generating stock image prompt for: unknown
2026-02-23 21:43:43,638 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:43:43,639 INFO src.apis.claude_api: Claude API response: model=claude-sonnet-4-20250514 input_tokens=2235 output_tokens=323 cost=$0.0115 (session total: input=55670 output=9003 cost=$0.2189)
2026-02-23 21:43:43,639 INFO src.generate_pin_content: Stock search query for W9-25: 'air fryer chicken dinner plate overhead'
2026-02-23 21:43:43,639 INFO src.apis.image_stock: Searching Unsplash: 'air fryer chicken dinner plate overhead' (orientation=portrait, count=10)
2026-02-23 21:43:44,153 INFO src.apis.image_stock: Unsplash returned 10 results for 'air fryer chicken dinner plate overhead'.
2026-02-23 21:43:44,154 INFO src.apis.image_stock: Searching Pexels: 'air fryer chicken dinner plate overhead' (orientation=portrait, count=10)
2026-02-23 21:43:44,842 INFO src.apis.image_stock: Pexels returned 10 results for 'air fryer chicken dinner plate overhead'.
2026-02-23 21:43:44,843 INFO src.apis.image_stock: Stock photo search for 'air fryer chicken dinner plate overhead': 20 total candidates.
2026-02-23 21:43:45,012 INFO src.apis.claude_api: Ranking 5 stock candidates for pin W9-25 (template: listicle-pin)
2026-02-23 21:43:48,906 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:43:48,906 INFO src.apis.claude_api: Claude API response: model=claude-haiku-4-5-20251001 input_tokens=1423 output_tokens=287 cost=$0.0023 (session total: input=57093 output=9290 cost=$0.2212)
2026-02-23 21:43:48,906 INFO src.apis.claude_api: Stock ranking complete. Top score: 8.0 (Overhead flat-lay of chicken with greens and vegetables on w), lowest: 2.0
2026-02-23 21:43:48,907 INFO src.apis.image_stock: Downloading image from unsplash: https://images.unsplash.com/photo-1613360734521-adef8a377347?crop=entropy&cs=srg
2026-02-23 21:43:49,376 INFO src.apis.image_stock: Image downloaded: unsplash:jF89MwHjfvg (143902 bytes) -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-25-hero.jpg
2026-02-23 21:43:49,377 INFO src.generate_pin_content: Downloaded stock image for W9-25: unsplash:unsplash:jF89MwHjfvg (score: 8.0)
2026-02-23 21:43:49,378 INFO src.pin_assembler: Rendering listicle-pin variant A -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-25.png
2026-02-23 21:43:52,175 INFO src.pin_assembler: Converted to JPEG: 139079 bytes (was 722821 bytes PNG)
2026-02-23 21:43:52,175 INFO src.pin_assembler: Pin rendered successfully: /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-25.png (139079 bytes)
2026-02-23 21:43:52,338 INFO __main__: Uploaded regen pin W9-25 to GCS: https://storage.googleapis.com/slated-pipeline-pins/W9-25.png
2026-02-23 21:43:52,561 INFO src.apis.sheets_api: Updated Content Queue row 36 (4 cells).
2026-02-23 21:43:52,561 INFO __main__: Regenerating regen_image for W9-26 (type=pin, feedback='this should be a stock image not a template')
2026-02-23 21:43:52,562 INFO __main__: Regenerating image for W9-26
2026-02-23 21:43:52,562 INFO src.apis.claude_api: Generating stock image prompt for: unknown
2026-02-23 21:43:58,667 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:43:58,668 INFO src.apis.claude_api: Claude API response: model=claude-sonnet-4-20250514 input_tokens=2226 output_tokens=314 cost=$0.0114 (session total: input=59319 output=9604 cost=$0.2326)
2026-02-23 21:43:58,668 INFO src.generate_pin_content: Stock search query for W9-26: 'grilled chicken protein dinner plate overhead'
2026-02-23 21:43:58,668 INFO src.apis.image_stock: Searching Unsplash: 'grilled chicken protein dinner plate overhead' (orientation=portrait, count=10)
2026-02-23 21:43:59,214 INFO src.apis.image_stock: Unsplash returned 10 results for 'grilled chicken protein dinner plate overhead'.
2026-02-23 21:43:59,214 INFO src.apis.image_stock: Searching Pexels: 'grilled chicken protein dinner plate overhead' (orientation=portrait, count=10)
2026-02-23 21:43:59,620 INFO src.apis.image_stock: Pexels returned 10 results for 'grilled chicken protein dinner plate overhead'.
2026-02-23 21:43:59,621 INFO src.apis.image_stock: Stock photo search for 'grilled chicken protein dinner plate overhead': 20 total candidates.
2026-02-23 21:43:59,790 INFO src.apis.claude_api: Ranking 5 stock candidates for pin W9-26 (template: tip-pin)
2026-02-23 21:44:03,934 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:44:03,935 INFO src.apis.claude_api: Claude API response: model=claude-haiku-4-5-20251001 input_tokens=1407 output_tokens=320 cost=$0.0024 (session total: input=60726 output=9924 cost=$0.2350)
2026-02-23 21:44:03,935 INFO src.apis.claude_api: Stock ranking complete. Top score: 9.0 (Excellent overhead composition of a protein-rich bowl with v), lowest: 2.0
2026-02-23 21:44:03,935 INFO src.apis.image_stock: Downloading image from unsplash: https://images.unsplash.com/photo-1761315600943-d8a5bb0c499f?crop=entropy&cs=srg
2026-02-23 21:44:03,990 INFO src.apis.image_stock: Image downloaded: unsplash:9TogNg01qzI (216645 bytes) -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-26-hero.jpg
2026-02-23 21:44:03,990 INFO src.generate_pin_content: Downloaded stock image for W9-26: unsplash:unsplash:9TogNg01qzI (score: 9.0)
2026-02-23 21:44:03,991 INFO src.pin_assembler: Rendering tip-pin variant A -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-26.png
2026-02-23 21:44:07,334 INFO src.pin_assembler: Converted to JPEG: 136485 bytes (was 848880 bytes PNG)
2026-02-23 21:44:07,334 INFO src.pin_assembler: Pin rendered successfully: /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-26.png (136485 bytes)
2026-02-23 21:44:07,494 INFO __main__: Uploaded regen pin W9-26 to GCS: https://storage.googleapis.com/slated-pipeline-pins/W9-26.png
2026-02-23 21:44:07,844 INFO src.apis.sheets_api: Updated Content Queue row 37 (4 cells).
2026-02-23 21:44:07,844 INFO __main__: Regenerating regen_image for W9-27 (type=pin, feedback='this is a picture of flowers. the recipe is pasta primavera with vegetables')
2026-02-23 21:44:07,844 INFO __main__: Regenerating image for W9-27
2026-02-23 21:44:07,844 INFO src.apis.claude_api: Generating stock image prompt for: unknown
2026-02-23 21:44:13,759 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:44:13,759 INFO src.apis.claude_api: Claude API response: model=claude-sonnet-4-20250514 input_tokens=2231 output_tokens=327 cost=$0.0116 (session total: input=62957 output=10251 cost=$0.2466)
2026-02-23 21:44:13,760 INFO src.generate_pin_content: Stock search query for W9-27: 'pasta primavera vegetables overhead spring'
2026-02-23 21:44:13,760 INFO src.apis.image_stock: Searching Unsplash: 'pasta primavera vegetables overhead spring' (orientation=portrait, count=10)
2026-02-23 21:44:14,302 INFO src.apis.image_stock: Unsplash returned 10 results for 'pasta primavera vegetables overhead spring'.
2026-02-23 21:44:14,303 INFO src.apis.image_stock: Searching Pexels: 'pasta primavera vegetables overhead spring' (orientation=portrait, count=10)
2026-02-23 21:44:14,731 INFO src.apis.image_stock: Pexels returned 10 results for 'pasta primavera vegetables overhead spring'.
2026-02-23 21:44:14,732 INFO src.apis.image_stock: Stock photo search for 'pasta primavera vegetables overhead spring': 20 total candidates.
2026-02-23 21:44:16,676 INFO src.apis.claude_api: Ranking 5 stock candidates for pin W9-27 (template: recipe-pin)
2026-02-23 21:44:19,395 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:44:19,396 INFO src.apis.claude_api: Claude API response: model=claude-haiku-4-5-20251001 input_tokens=1420 output_tokens=240 cost=$0.0021 (session total: input=64377 output=10491 cost=$0.2487)
2026-02-23 21:44:19,396 INFO src.apis.claude_api: Stock ranking complete. Top score: 3.0 (Related to vegetables but shows only flower buds/unopened bl), lowest: 2.0
2026-02-23 21:44:19,396 WARNING src.generate_pin_content: All stock candidates scored < 6.5 for pin W9-27 (best: 3.0), retrying search
2026-02-23 21:44:19,396 INFO src.apis.claude_api: Generating stock_retry image prompt for: unknown
2026-02-23 21:44:25,747 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:44:25,748 INFO src.apis.claude_api: Claude API response: model=claude-sonnet-4-20250514 input_tokens=2285 output_tokens=329 cost=$0.0118 (session total: input=66662 output=10820 cost=$0.2605)
2026-02-23 21:44:25,748 INFO src.apis.image_stock: Searching Unsplash: 'pasta primavera vegetables overhead colorful' (orientation=portrait, count=10)
2026-02-23 21:44:26,076 INFO src.apis.image_stock: Unsplash returned 0 results for 'pasta primavera vegetables overhead colorful'.
2026-02-23 21:44:26,077 INFO src.apis.image_stock: Searching Pexels: 'pasta primavera vegetables overhead colorful' (orientation=portrait, count=10)
2026-02-23 21:44:26,541 INFO src.apis.image_stock: Pexels returned 10 results for 'pasta primavera vegetables overhead colorful'.
2026-02-23 21:44:26,542 INFO src.apis.image_stock: Stock photo search for 'pasta primavera vegetables overhead colorful': 10 total candidates.
2026-02-23 21:44:29,241 INFO src.apis.claude_api: Ranking 5 stock candidates for pin W9-27 (template: recipe-pin)
2026-02-23 21:44:33,892 INFO httpx: HTTP Request: POST https://api.anthropic.com/v1/messages "HTTP/1.1 200 OK"
2026-02-23 21:44:33,893 INFO src.apis.claude_api: Claude API response: model=claude-haiku-4-5-20251001 input_tokens=1404 output_tokens=358 cost=$0.0026 (session total: input=68066 output=11178 cost=$0.2630)
2026-02-23 21:44:33,893 INFO src.apis.claude_api: Stock ranking complete. Top score: 8.0 (Excellent match — finished pasta primavera with vegetables i), lowest: 2.0
2026-02-23 21:44:33,893 INFO src.apis.image_stock: Downloading image from pexels: https://images.pexels.com/photos/15057293/pexels-photo-15057293.jpeg
2026-02-23 21:44:34,580 INFO src.apis.image_stock: Image downloaded: pexels:15057293 (603941 bytes) -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-27-hero.jpg
2026-02-23 21:44:34,581 INFO src.generate_pin_content: Downloaded stock image for W9-27: pexels:pexels:15057293 (score: 8.0)
2026-02-23 21:44:34,581 INFO src.pin_assembler: Rendering recipe-pin variant A -> /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-27.png
2026-02-23 21:44:37,335 INFO src.pin_assembler: Converted to JPEG: 219181 bytes (was 1380676 bytes PNG)
2026-02-23 21:44:37,335 INFO src.pin_assembler: Pin rendered successfully: /home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W9-27.png (219181 bytes)
2026-02-23 21:44:37,506 INFO __main__: Uploaded regen pin W9-27 to GCS: https://storage.googleapis.com/slated-pipeline-pins/W9-27.png
2026-02-23 21:44:37,875 INFO src.apis.sheets_api: Updated Content Queue row 38 (4 cells).
2026-02-23 21:44:37,877 INFO __main__: Saved updated pin generation results
2026-02-23 21:44:38,234 INFO src.apis.sheets_api: Reset regen trigger to 'idle'.
2026-02-23 21:44:38,234 INFO src.apis.slack_notify: Sending Slack notification: 15 regenerated, 6 failed -- ready for re-review.
2026-02-23 21:44:38,364 INFO __main__: Regen complete: 15 succeeded, 6 failed out of 21 requests