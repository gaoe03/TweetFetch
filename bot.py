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
    await ctx.send(f"Found **{total_results}** media results. Do you want to continue? (Y/N)")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ["y", "n"]

    try:
        msg = await bot.wait_for("message", timeout=30.0, check=check)
        if msg.content.lower() == "n":
            abort_flag[ctx.author.id] = True
            await ctx.send("Cancelled.")
            return
    except asyncio.TimeoutError:
        await ctx.send("Timed out. Try again.")
        return

    for tweet in filtered_tweets:
        username_time = f"{tweet['username']}"  # Used for markdown links

        videos = [url for url in tweet["media"] if url.endswith('.mp4')]
        images = [url for url in tweet["media"] if not url.endswith('.mp4')]

        # Send video links separately using markdown format
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

        # Send images normally
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
            await asyncio.sleep(0.5)

    await ctx.send("Finished sending all media! ✅")



@bot.command()
async def richcompile(ctx, *args):
    """Fetch full tweets by username and/or date (year, month, day)."""
    abort_flag[ctx.author.id] = False  

    username, year, month, day = parse_date_filters(args)
    filtered_tweets = filter_tweets(username, year, month, day)

    if not filtered_tweets:
        await ctx.send("No matching tweets found.")
        return

    await ctx.send(f"Found **{len(filtered_tweets)}** tweets. Do you want to continue? (Y/N)")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ["y", "n"]

    try:
        msg = await bot.wait_for("message", timeout=30.0, check=check)
        if msg.content.lower() == "n":
            abort_flag[ctx.author.id] = True
            await ctx.send("Cancelled.")
            return
    except asyncio.TimeoutError:
        await ctx.send("Timed out. Try again.")
        return

    for tweet in filtered_tweets:
        if abort_flag[ctx.author.id]:
            await ctx.send("Processing stopped.")
            return

        try:
            timestamp_dt = datetime.datetime.strptime(tweet["created_at"], "%a %b %d %H:%M:%S %z %Y")
            formatted_timestamp = timestamp_dt.strftime("%m/%d/%Y %I:%M %p").replace(" 0", " ")
            username_time = f"{tweet['username']} {formatted_timestamp}"

            embed = discord.Embed(description=tweet["text"], color=discord.Color.blue())
            embed.set_author(name=tweet["username"], url=f"https://twitter.com/{tweet['username']}/status/{tweet['tweet_id']}")
            embed.set_footer(text=username_time)

            if len(tweet["media"]) == 1:  # One image, embed inside the tweet
                embed.set_image(url=tweet["media"][0])

            await ctx.send(embed=embed)

            # Handle multiple images
            if len(tweet["media"]) > 1:
                for index, media_url in enumerate(tweet["media"], start=1):
                    media_embed = discord.Embed(color=discord.Color.blue())
                    media_embed.set_image(url=media_url)
                    media_embed.set_footer(text=f"{username_time} ({index}/{len(tweet['media'])})")
                    await ctx.send(embed=media_embed)
                    await asyncio.sleep(0.5)

            # Handle videos separately
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
    top_users = user_counts.most_common(10)

    # Longest Tweet Liked
    longest_tweet = max(tweets, key=lambda t: len(t["tweet_text"]), default=None)

    # If a specific stat is requested
    if args:
        stat_type = args[0].lower()

        if stat_type == "top_users":
            # Same format as "Most Liked Users" from .stats, but as plain text
            user_list = "\n".join([f"[{user}](<https://twitter.com/{user}>) ({count})" for user, count in top_users])
            await ctx.send(f"🏆 **Top 10 Most Liked Users**\n{user_list}")
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
    top_users_text = "\n".join([f"[{user}](<https://twitter.com/{user}>) ({count})" for user, count in top_users])
    embed.add_field(name="🏆 Most Liked Users", value=top_users_text, inline=False)

    await ctx.send(embed=embed)


bot.run(TOKEN)
