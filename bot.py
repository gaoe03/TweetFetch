import discord
import json
import asyncio
import datetime
import calendar
import urllib.parse
import collections
import random
from discord.ext import commands

# Load config
with open("config.json", "r") as f:
    config = json.load(f)

TOKEN = config["TOKEN"]
JSON_FILE = config["JSON_FILE"]

# Set up bot
intents = discord.Intents.default()
intents.message_content = True  # Enables message content intent
bot = commands.Bot(command_prefix=".", intents=intents)

abort_flag = {}

MONTH_MAP = {m.lower(): str(i).zfill(2) for i, m in enumerate(calendar.month_name) if m}
MONTH_ABBR_MAP = {m.lower(): str(i).zfill(2) for i, m in enumerate(calendar.month_abbr) if m}

def load_tweets():
    """Load tweets from JSON file."""
    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return []

def clean_media_url(url):
    """Remove query parameters (like ?tag=12) from media URLs."""
    parsed_url = urllib.parse.urlparse(url)
    clean_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
    return clean_url

def parse_date_filters(args):
    """Extract year, month, and day from user input."""
    year, month, day = None, None, None
    remaining_args = []

    for arg in args:
        if arg.isdigit() and len(arg) == 4:  # Year (e.g., 2025)
            year = arg
        elif arg.isdigit() and 1 <= int(arg) <= 12:  # Month (numeric)
            month = str(arg).zfill(2)
        elif arg.lower() in MONTH_MAP:  # Month (full name)
            month = MONTH_MAP[arg.lower()]
        elif arg.lower() in MONTH_ABBR_MAP:  # Month (abbreviation)
            month = MONTH_ABBR_MAP[arg.lower()]
        elif arg.isdigit() and 1 <= int(arg) <= 31:  # Day
            day = str(arg).zfill(2)
        else:
            remaining_args.append(arg)  # Keep non-date arguments (likely username)

    username = " ".join(remaining_args) if remaining_args else None
    return username, year, month, day

def filter_tweets(username=None, year=None, month=None, day=None):
    """Filter tweets based on username and/or date (year, month, day)."""
    tweets = load_tweets()
    filtered_tweets = []

    for tweet in tweets:
        tweet_time = tweet.get("tweet_created_at", "")
        tweet_username = tweet.get("user_handle", "")
        tweet_text = tweet.get("tweet_text", "")
        media = [clean_media_url(url) for url in tweet.get("tweet_media_urls", [])]  # Clean URLs
        tweet_id = tweet.get("tweet_id", "")

        try:
            tweet_dt = datetime.datetime.strptime(tweet_time, "%a %b %d %H:%M:%S %z %Y")
            tweet_year = str(tweet_dt.year)
            tweet_month = str(tweet_dt.month).zfill(2)
            tweet_day = str(tweet_dt.day).zfill(2)
        except ValueError:
            continue  # Skip if date parsing fails

        if media and (
            (not username or username.lower() in tweet_username.lower()) and
            (not year or year == tweet_year) and
            (not month or month == tweet_month) and
            (not day or day == tweet_day)
        ):
            filtered_tweets.append({
                "username": tweet_username,
                "created_at": tweet_time,
                "text": tweet_text,
                "media": media,
                "tweet_id": tweet_id
            })

    return filtered_tweets

@bot.command()
async def stop(ctx):
    """Allows the user to manually stop ongoing processes like .compile and .game."""
    if ctx.author.id in abort_flag:
        abort_flag[ctx.author.id] = True
        await ctx.send("⛔ **Process aborted.**")
    else:
        await ctx.send("⚠ No active process to stop.")


@bot.command()
async def ping(ctx):
    """Responds with Pong! and the bot's latency."""
    latency = round(bot.latency * 1000)  # Convert to milliseconds
    await ctx.send(f"Pong! 🏓 {latency}ms")

@bot.command()
async def compile(ctx, *args):
    """Fetch tweets by username and/or date (year, month, day)."""
    abort_flag[ctx.author.id] = False

    username, year, month, day = parse_date_filters(args)
    filtered_tweets = filter_tweets(username, year, month, day)

    if not filtered_tweets:
        await ctx.send("No matching media found.")
        return

    total_results = sum(len(tweet["media"]) for tweet in filtered_tweets)
    await ctx.send(
        f"Found **{total_results}** media results. Choose an option:\n"
        "-# 1. **Slideshow**\n"
        "-# 2. **All at once**\n"
        "-# 3. **Exit**"
    )

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content in ["1", "2", "3"]

    try:
        msg = await bot.wait_for("message", timeout=30.0, check=check)
        choice = msg.content

        if choice == "3":
            abort_flag[ctx.author.id] = True
            await ctx.send("Cancelled.")
            return
        elif choice not in ["1", "2"]:
            await ctx.send("Invalid option. Please respond with `1`, `2`, or `3`.")
            msg = await bot.wait_for("message", timeout=15.0, check=check)
            if msg.content not in ["1", "2"]:
                await ctx.send("Invalid response again. Cancelling.")
                return
            choice = msg.content  
    except asyncio.TimeoutError:
        await ctx.send("Timed out. Try again.")
        return

    if choice == "1":
        await send_slideshow(ctx, filtered_tweets)
    elif choice == "2":
        await send_all(ctx, filtered_tweets)

async def send_all(ctx, filtered_tweets):
    """Sends all media results at once."""
    for tweet in filtered_tweets:
        if abort_flag[ctx.author.id]:
            await ctx.send("Processing stopped.")
            return

        username_time = f"{tweet['username']}"  

        videos = [url for url in tweet["media"] if url.endswith('.mp4')]
        images = [url for url in tweet["media"] if not url.endswith('.mp4')]

        # Send video links separately
        if videos:
            for index, video_url in enumerate(videos, start=1):
                if len(videos) > 1:
                    await ctx.send(f"[{username_time} ({index}/{len(videos)})]({video_url})")
                else:
                    await ctx.send(f"[{username_time}]({video_url})")

            # Extra embed with just the username after videos
            video_embed = discord.Embed(color=discord.Color.blue())
            video_embed.set_footer(text=username_time)
            await ctx.send(embed=video_embed)

        # Send images
        for index, media_url in enumerate(images, start=1):
            if abort_flag[ctx.author.id]:
                await ctx.send("Processing stopped.")
                return

            embed = discord.Embed(color=discord.Color.blue())
            embed.set_image(url=media_url)

            if len(images) > 1:
                embed.set_footer(text=f"{tweet['username']} ({index}/{len(images)})")
            else:
                embed.set_footer(text=f"{tweet['username']}")

            await ctx.send(embed=embed)
            await asyncio.sleep(0.5)  # Prevent rate limit issues

    await ctx.send("Finished sending all media! ✅")


async def send_slideshow(ctx, filtered_tweets):
    """Displays tweets in a slideshow format with reaction navigation."""
    current_index = 0
    tweet_count = len(filtered_tweets)

    def generate_embed(index):
        tweet = filtered_tweets[index]
        username_time = f"{tweet['username']}"

        embed = discord.Embed(color=discord.Color.blue())
        if tweet["media"]:
            embed.set_image(url=tweet["media"][0])
        embed.set_footer(text=f"{username_time} ({index + 1}/{tweet_count})")

        return embed

    msg = await ctx.send(embed=generate_embed(current_index))
    await msg.add_reaction("⏪")  # First page
    await msg.add_reaction("⬅️")  # Previous page
    await msg.add_reaction("➡️")  # Next page
    await msg.add_reaction("⏩")  # Last page

    def check_reaction(reaction, user):
        return user == ctx.author and reaction.message.id == msg.id and str(reaction.emoji) in ["⬅️", "➡️", "⏪", "⏩"]

    while True:
        try:
            reaction, user = await bot.wait_for("reaction_add", timeout=60.0, check=check_reaction)

            if str(reaction.emoji) == "➡️" and current_index < tweet_count - 1:
                current_index += 1
            elif str(reaction.emoji) == "⬅️" and current_index > 0:
                current_index -= 1
            elif str(reaction.emoji) == "⏪":
                current_index = 0  # First page
            elif str(reaction.emoji) == "⏩":
                current_index = tweet_count - 1  # Last page

            await msg.edit(embed=generate_embed(current_index))
            await msg.remove_reaction(reaction.emoji, user)

        except asyncio.TimeoutError:
            break  # Auto-exit after 60 sec of no interaction

@bot.command()
async def richcompile(ctx, *args):
    """Fetch full tweets by username and/or date (year, month, day)."""
    abort_flag[ctx.author.id] = False  

    username, year, month, day = parse_date_filters(args)
    filtered_tweets = filter_tweets(username, year, month, day)

    if not filtered_tweets:
        await ctx.send("No matching tweets found.")
        return

    await ctx.send(
        f"Found **{len(filtered_tweets)}** tweets. Choose an option:\n"
        "-# 1. **Slideshow**\n"
        "-# 2. **All at once**\n"
        "-# 3. **Exit**"
    )

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content in ["1", "2", "3"]

    try:
        msg = await bot.wait_for("message", timeout=30.0, check=check)
        choice = msg.content

        if choice == "3":
            abort_flag[ctx.author.id] = True
            await ctx.send("Cancelled.")
            return
        elif choice not in ["1", "2"]:
            await ctx.send("Invalid option. Please respond with `1`, `2`, or `3`.")
            msg = await bot.wait_for("message", timeout=15.0, check=check)
            if msg.content not in ["1", "2"]:
                await ctx.send("Invalid response again. Cancelling.")
                return
            choice = msg.content  
    except asyncio.TimeoutError:
        await ctx.send("Timed out. Try again.")
        return

    if choice == "1":
        await send_rich_slideshow(ctx, filtered_tweets)
    elif choice == "2":
        await send_rich_all(ctx, filtered_tweets)

async def send_rich_all(ctx, filtered_tweets):
    """Displays all tweets with full details at once."""
    for tweet in filtered_tweets:
        if abort_flag[ctx.author.id]:
            await ctx.send("Processing stopped.")
            return

        try:
            timestamp_dt = datetime.datetime.strptime(tweet["created_at"], "%a %b %d %H:%M:%S %z %Y")
            formatted_timestamp = timestamp_dt.strftime("%m/%d/%Y %I:%M %p").replace(" 0", " ")
            username_time = f"{tweet['username']} {formatted_timestamp}"

            # Tweet Embed
            embed = discord.Embed(description=tweet["text"], color=discord.Color.blue())
            embed.set_author(name=tweet["username"], url=f"https://twitter.com/{tweet['username']}/status/{tweet['tweet_id']}")
            embed.set_footer(text=username_time)

            if len(tweet["media"]) == 1:  # One image, embed inside tweet
                embed.set_image(url=tweet["media"][0])

            await ctx.send(embed=embed)

            # Multiple images (if any)
            if len(tweet["media"]) > 1:
                for index, media_url in enumerate(tweet["media"], start=1):
                    media_embed = discord.Embed(color=discord.Color.blue())
                    media_embed.set_image(url=media_url)
                    media_embed.set_footer(text=f"{username_time} ({index}/{len(tweet['media'])})")
                    await ctx.send(embed=media_embed)
                    await asyncio.sleep(0.5)

            # Videos
            videos = [url for url in tweet["media"] if url.endswith('.mp4')]
            if videos:
                for index, video_url in enumerate(videos, start=1):
                    if len(videos) > 1:
                        await ctx.send(f"[{username_time} ({index}/{len(videos)})]({video_url})")
                    else:
                        await ctx.send(f"[{username_time}]({video_url})")

            await asyncio.sleep(1)

        except Exception as e:
            print(f"Error processing tweet: {e}")

    await ctx.send("Finished sending all tweets! ✅")

async def send_rich_slideshow(ctx, filtered_tweets):
    """Displays tweets in a rich slideshow format with reaction navigation."""
    current_index = 0
    tweet_count = len(filtered_tweets)

    def generate_embed(index):
        tweet = filtered_tweets[index]
        timestamp_dt = datetime.datetime.strptime(tweet["created_at"], "%a %b %d %H:%M:%S %z %Y")
        formatted_timestamp = timestamp_dt.strftime("%m/%d/%Y %I:%M %p").replace(" 0", " ")
        username_time = f"{tweet['username']} {formatted_timestamp}"

        embed = discord.Embed(description=tweet["text"], color=discord.Color.blue())
        embed.set_author(name=tweet["username"], url=f"https://twitter.com/{tweet['username']}/status/{tweet['tweet_id']}")
        embed.set_footer(text=f"{username_time} ({index + 1}/{tweet_count})")

        if tweet["media"]:
            embed.set_image(url=tweet["media"][0])  # First image/video in slideshow

        return embed

    msg = await ctx.send(embed=generate_embed(current_index))
    await msg.add_reaction("⏪")  # First page
    await msg.add_reaction("⬅️")  # Previous page
    await msg.add_reaction("➡️")  # Next page
    await msg.add_reaction("⏩")  # Last page

    def check_reaction(reaction, user):
        return user == ctx.author and reaction.message.id == msg.id and str(reaction.emoji) in ["⬅️", "➡️", "⏪", "⏩"]

    while True:
        try:
            reaction, user = await bot.wait_for("reaction_add", timeout=60.0, check=check_reaction)

            if str(reaction.emoji) == "➡️" and current_index < tweet_count - 1:
                current_index += 1
            elif str(reaction.emoji) == "⬅️" and current_index > 0:
                current_index -= 1
            elif str(reaction.emoji) == "⏪":
                current_index = 0  # First page
            elif str(reaction.emoji) == "⏩":
                current_index = tweet_count - 1  # Last page

            await msg.edit(embed=generate_embed(current_index))
            await msg.remove_reaction(reaction.emoji, user)

        except asyncio.TimeoutError:
            break  # Auto-exit after 60 sec of no interaction


@bot.command()
async def stats(ctx, *args):
    """Fetches statistics from liked tweets and displays them in an embed."""
    tweets = load_tweets()
    if not tweets:
        await ctx.send("No data available.")
        return

    # Count total tweets & media
    total_tweets = len(tweets)
    total_images = sum(1 for tweet in tweets for media in tweet["tweet_media_urls"] if media.endswith(('.jpg', '.png', '.jpeg')))
    total_videos = sum(1 for tweet in tweets for media in tweet["tweet_media_urls"] if media.endswith('.mp4'))
    total_media = total_images + total_videos

    # Most liked users
    user_counts = collections.Counter(tweet["user_handle"] for tweet in tweets)
    top_users = user_counts.most_common()

    # Longest Tweet Liked
    longest_tweet = max(tweets, key=lambda t: len(t["tweet_text"]), default=None)

    # If a specific stat is requested
    if args:
        stat_type = args[0].lower()

        if stat_type == "top_users":
            if not top_users:
                await ctx.send("No liked users found.")
                return

            per_page = 10  # Users per page
            total_pages = (len(top_users) - 1) // per_page + 1
            current_page = 0

            def generate_embed(page):
                """Generates the embed for the given page number."""
                start_idx = page * per_page
                end_idx = start_idx + per_page
                page_users = top_users[start_idx:end_idx]

                embed = discord.Embed(title="🏆 Top 10 Most Liked Users", color=discord.Color.blue())
                for user, count in page_users:
                    embed.add_field(name=f"``{user}``", value=f"{count} liked tweets", inline=False)

                embed.set_footer(text=f"Page {page + 1}/{total_pages}")
                return embed

            # Send initial embed
            msg = await ctx.send(embed=generate_embed(current_page))

            # Add reaction buttons for pagination
            await msg.add_reaction("⏪")  # First page
            await msg.add_reaction("⬅️")  # Previous page
            await msg.add_reaction("➡️")  # Next page
            await msg.add_reaction("⏩")  # Last page

            def check_reaction(reaction, user):
                return user == ctx.author and reaction.message.id == msg.id and str(reaction.emoji) in ["⬅️", "➡️", "⏪", "⏩"]

            while True:
                try:
                    reaction, user = await bot.wait_for("reaction_add", timeout=60.0, check=check_reaction)

                    if str(reaction.emoji) == "➡️" and current_page < total_pages - 1:
                        current_page += 1
                    elif str(reaction.emoji) == "⬅️" and current_page > 0:
                        current_page -= 1
                    elif str(reaction.emoji) == "⏪":
                        current_page = 0  # First page
                    elif str(reaction.emoji) == "⏩":
                        current_page = total_pages - 1  # Last page

                    await msg.edit(embed=generate_embed(current_page))
                    await msg.remove_reaction(reaction.emoji, user)  # Remove reaction after use

                except asyncio.TimeoutError:
                    break  # Exit loop after timeout

            return

        elif stat_type == "media":
            embed = discord.Embed(title="📊 Media Breakdown", color=discord.Color.blue())
            embed.add_field(name="📸 Images", value=f"{total_images}", inline=True)
            embed.add_field(name="🎥 Videos", value=f"{total_videos}", inline=True)
            await ctx.send(embed=embed)
            return

        elif stat_type == "longest":
            embed = discord.Embed(title="📜 Longest Tweet Liked", description=longest_tweet["tweet_text"], color=discord.Color.blue())
            embed.set_author(name=longest_tweet["user_handle"], url=f"https://twitter.com/{longest_tweet['user_handle']}/status/{longest_tweet['tweet_id']}")
            embed.set_footer(text=f"Length: {len(longest_tweet['tweet_text'])} characters")
            await ctx.send(embed=embed)
            return

        else:
            await ctx.send("Invalid stats type. Available: `top_users`, `media`, `longest`")
            return

    # Full stats embed
    embed = discord.Embed(title="📊 Tweet Stats", color=discord.Color.blue())
    embed.add_field(name="📝 Total Tweets", value=f"{total_tweets}", inline=True)
    embed.add_field(name="📸 Total Media", value=f"{total_media}", inline=True)
    embed.add_field(name="📸 Images", value=f"{total_images}", inline=True)
    embed.add_field(name="🎥 Videos", value=f"{total_videos}", inline=True)

    # Top Users (embedded in .stats)
    top_users_text = "\n".join([f"``{user}`` ({count})" for user, count in top_users[:10]])
    embed.add_field(name="🏆 Most Liked Users", value=top_users_text, inline=False)

    await ctx.send(embed=embed)


game_in_progress = {}
@bot.command()
async def game(ctx):
    """Starts a game where users guess the Tweeter from a random liked tweet image."""
    if game_in_progress.get(ctx.channel.id, False):
        await ctx.send("⚠ **Game already in progress!** Please wait for it to finish.")
        return

    game_in_progress[ctx.channel.id] = True

    tweets = load_tweets()
    if not tweets:
        await ctx.send("No data available.")
        game_in_progress[ctx.channel.id] = False
        return

    # Choose a random tweet with media
    valid_tweets = [tweet for tweet in tweets if tweet["tweet_media_urls"]]
    if not valid_tweets:
        await ctx.send("No media found in liked tweets.")
        game_in_progress[ctx.channel.id] = False
        return

    tweet = random.choice(valid_tweets)
    username = tweet["user_handle"]
    image_url = random.choice(tweet["tweet_media_urls"])
    game_starter = ctx.author

    # Send the tweet image (No username, No timestamp)
    embed = discord.Embed(title="Guess the Tweeter!", description="Who posted this image?")
    embed.set_image(url=image_url)
    msg = await ctx.send(embed=embed)

    # Add the shrug emoji reaction
    shrug_emoji = "🤷"
    await msg.add_reaction(shrug_emoji)

    correct_answer = username.lower()
    hint_1_given = False
    hint_2_given = False

    def check(msg):
        return msg.author == ctx.author and msg.channel == ctx.channel

    def reaction_check(reaction, user):
        return user == game_starter and str(reaction.emoji) == shrug_emoji and reaction.message.id == msg.id

    try:
        # Create tasks for hints and timeout
        hint_1_task = asyncio.create_task(asyncio.sleep(15))  # First hint at 15 sec
        hint_2_task = asyncio.create_task(asyncio.sleep(24))  # Second hint at 24 sec
        timeout_task = asyncio.create_task(asyncio.sleep(30))  # Timeout at 30 sec
        message_task = asyncio.create_task(bot.wait_for("message", check=check))
        reaction_task = asyncio.create_task(bot.wait_for("reaction_add", check=reaction_check))

        while True:
            done, pending = await asyncio.wait(
                [message_task, hint_1_task, hint_2_task, timeout_task, reaction_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            if reaction_task in done:
                await ctx.send(f"🤷 **Game ended!** The correct answer was **{username}**.\n-# Type `.game` to play again!")
                game_in_progress[ctx.channel.id] = False
                return

            if hint_1_task in done and not hint_1_given:
                hint_1_given = True
                hint_type = random.choice(["partial", "like_count"])

                if hint_type == "partial":
                    revealed = list(username)
                    for i in range(1, len(revealed) - 1):
                        if random.random() > 0.5:
                            revealed[i] = "_"
                    hint = "".join(revealed)
                    await ctx.send(f"**Hint:** ``{hint}``")  # Uses backticks to prevent markdown issues
                else:
                    like_count = sum(1 for t in tweets if t["user_handle"] == username)
                    await ctx.send(f"**Hint:** You have liked this Tweeter **{like_count} times**.")
                continue  # Keep waiting for a guess


            if hint_2_task in done and not hint_2_given:
                hint_2_given = True
                await ctx.send(f"**Hint:** The username starts with **{username[0].upper()}** and ends with **{username[-1].upper()}**!")
                continue  # Keep waiting for a guess

            if timeout_task in done:
                await ctx.send(f"⏳ **Time's up!** The correct answer was **{username}**.\n-# Type `.game` to play again!")
                game_in_progress[ctx.channel.id] = False
                return

            if message_task in done:
                guess_msg = message_task.result()
                guess = guess_msg.content.lower()

                if guess == correct_answer:
                    await ctx.send(f"✅ **Correct!** The Tweeter was **{username}**! 🎉\n-# Type `.game` to play again!")
                    game_in_progress[ctx.channel.id] = False
                    return  # Stop the game if the guess is correct

                # Reset the message task to wait for another guess
                message_task = asyncio.create_task(bot.wait_for("message", check=check))

    except asyncio.TimeoutError:
        await ctx.send(f"⏳ **Time's up!** The correct answer was **{username}**.\n -# Type `.game` to play again!")
    finally:
        game_in_progress[ctx.channel.id] = False  # Ensure game flag is reset if anything goes wrong

bot.run(TOKEN)
