import discord
import json
import asyncio
import datetime
import calendar
import urllib.parse
import collections
import random
import os
from discord.ext import commands

# Folder discovery and validation
USERS_BASE_PATH = "/Users/gaoe/Downloads/projects/LikedTweets/users/"

def discover_user_folders():
    """Scan for available user folders containing liked_tweets.json"""
    if not os.path.exists(USERS_BASE_PATH):
        print(f"❌ Users directory not found: {USERS_BASE_PATH}")
        return {}
    
    user_folders = {}
    try:
        for folder_name in os.listdir(USERS_BASE_PATH):
            folder_path = os.path.join(USERS_BASE_PATH, folder_name)
            if os.path.isdir(folder_path):
                json_path = os.path.join(folder_path, "liked_tweets.json")
                if os.path.exists(json_path):
                    user_folders[folder_name] = json_path
    except Exception as e:
        print(f"❌ Error scanning user folders: {e}")
    
    return user_folders

def prompt_user_selection(available_folders):
    """Prompt user to select which folder/profile to use"""
    if not available_folders:
        print("❌ No user folders found with liked_tweets.json!")
        return None
    
    print("\n" + "="*50)
    print("📁 Available User Profiles:")
    print("="*50)
    
    folder_list = sorted(available_folders.keys())
    for idx, folder_name in enumerate(folder_list, 1):
        print(f"  {idx}. {folder_name}")
    
    print("="*50)
    
    while True:
        try:
            choice = input(f"\nSelect a profile (1-{len(folder_list)}): ").strip()
            choice_idx = int(choice) - 1
            
            if 0 <= choice_idx < len(folder_list):
                selected_folder = folder_list[choice_idx]
                print(f"✅ Selected: {selected_folder}\n")
                return selected_folder
            else:
                print(f"❌ Invalid choice. Please enter a number between 1 and {len(folder_list)}.")
        except (ValueError, KeyboardInterrupt):
            print("\n❌ Invalid input. Exiting.")
            exit()

def validate_and_update_config():
    """Always prompt user to select profile on startup"""
    config_path = "config.json"
    
    # Load existing config or create new one
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = json.load(f)
    else:
        print("⚠️  config.json not found! Creating new config...")
        config = {"TOKEN": "YOUR_BOT_TOKEN_HERE"}
    
    # Discover available folders
    available_folders = discover_user_folders()
    
    if not available_folders:
        print("❌ No user folders found! Please check your folder structure.")
        exit()
    
    # Always prompt for selection
    selected_folder = prompt_user_selection(available_folders)
    if not selected_folder:
        exit()
    
    # Build profiles dict from all available folders
    profiles = available_folders
    
    # Update config
    config["JSON_FILE"] = profiles
    config["SELECTED_PROFILE"] = selected_folder
    
    # Save updated config
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)
    
    print(f"✅ Config updated!")
    
    return config

# Load and validate config
config = validate_and_update_config()

TOKEN = config["TOKEN"]
# Support both string (legacy) and dict (profiles) for JSON_FILE
DEFAULT_JSON_FILE = config["JSON_FILE"]

# Determine active profile from config or use default
if "SELECTED_PROFILE" in config and isinstance(DEFAULT_JSON_FILE, dict):
    ACTIVE_PROFILE = config["SELECTED_PROFILE"]
else:
    ACTIVE_PROFILE = "default"

# Build PROFILES dict
PROFILES = {"default": DEFAULT_JSON_FILE} if isinstance(DEFAULT_JSON_FILE, str) else DEFAULT_JSON_FILE
CURRENT_JSON_PATH = PROFILES.get(ACTIVE_PROFILE, list(PROFILES.values())[0] if PROFILES else None)

if not CURRENT_JSON_PATH or not os.path.exists(CURRENT_JSON_PATH):
    print(f"❌ Error: Selected profile '{ACTIVE_PROFILE}' path not found: {CURRENT_JSON_PATH}")
    exit()

print(f"🚀 Starting bot with profile: {ACTIVE_PROFILE}")
print(f"📂 Using JSON file: {CURRENT_JSON_PATH}\n")

# Global Cache
TWEET_CACHE = []
CACHE_TIMESTAMP = None


# Set up bot
intents = discord.Intents.default()
intents.message_content = True  # Enables message content intent
bot = commands.Bot(command_prefix=".", intents=intents)
bot.remove_command("help") # Remove default help

abort_flag = {}

MONTH_MAP = {m.lower(): str(i).zfill(2) for i, m in enumerate(calendar.month_name) if m}
MONTH_ABBR_MAP = {m.lower(): str(i).zfill(2) for i, m in enumerate(calendar.month_abbr) if m}


USER_PREFS_FILE = "user_prefs.json"

def load_user_prefs():
    if os.path.exists(USER_PREFS_FILE):
        try:
            with open(USER_PREFS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading user prefs: {e}")
    return {}

def save_user_prefs():
    try:
        with open(USER_PREFS_FILE, "w") as f:
            json.dump(user_media_preferences, f)
    except Exception as e:
        print(f"Error saving user prefs: {e}")

user_media_preferences = load_user_prefs()  # Stores user preferences (jpg, mp4, etc)

def parse_tweet_date(tweet):
    """Helper to parse date from tweet and add structured fields."""
    try:
        tweet_time = tweet.get("tweet_created_at", "")
        tweet_dt = datetime.datetime.strptime(tweet_time, "%a %b %d %H:%M:%S %z %Y")
        tweet["parsed_year"] = str(tweet_dt.year)
        tweet["parsed_month"] = str(tweet_dt.month).zfill(2)
        tweet["parsed_day"] = str(tweet_dt.day).zfill(2)
        tweet["parsed_dt"] = tweet_dt # Store datetime object for sorting/formatting if needed
        return True
    except ValueError:
        return False

def load_tweets(force_reload=False):
    """Load tweets from JSON file with caching."""
    global TWEET_CACHE, CACHE_TIMESTAMP
    
    if not force_reload and TWEET_CACHE:
        return TWEET_CACHE

    print(f"Loading tweets from {CURRENT_JSON_PATH}...")
    try:
        with open(CURRENT_JSON_PATH, "r", encoding="utf-8") as f:
            tweets = json.load(f)
            
        # Pre-process tweets
        valid_tweets = []
        for tweet in tweets:
            if parse_tweet_date(tweet):
                valid_tweets.append(tweet)
        
        TWEET_CACHE = valid_tweets
        CACHE_TIMESTAMP = datetime.datetime.now()
        print(f"Loaded {len(TWEET_CACHE)} tweets.")
        return TWEET_CACHE
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

def filter_tweets(ctx, username=None, year=None, month=None, day=None):
    """Filter tweets based on username and/or date (year, month, day), respecting user media preferences."""
    tweets = load_tweets()
    filtered_tweets = []

    # Get user preference (default to "all")
    user_preference = user_media_preferences.get(str(ctx.author.id), "all") # Ensure ID is string for JSON compatibility

    for tweet in tweets:
        tweet_username = tweet.get("user_handle", "")
        tweet_text = tweet.get("tweet_content", "")
        
        # Use pre-parsed dates
        tweet_year = tweet.get("parsed_year")
        tweet_month = tweet.get("parsed_month")
        tweet_day = tweet.get("parsed_day")

        # Filter media based on user preference
        if user_preference != "all":
            media = [clean_media_url(url) for url in tweet.get("tweet_media_urls", []) if url.lower().startswith("https") and url.lower().split("?")[0].endswith(user_preference)]
        else:
            media = [clean_media_url(url) for url in tweet.get("tweet_media_urls", [])]

        tweet_id = tweet.get("tweet_id", "")

        if media and (
            (not username or username.lower() in tweet_username.lower()) and
            (not year or year == tweet_year) and
            (not month or month == tweet_month) and
            (not day or day == tweet_day)
        ):
            filtered_tweets.append({
                "username": tweet_username,
                "created_at": tweet.get("tweet_created_at", ""),
                "text": tweet_text,
                "media": media,
                "tweet_id": tweet_id
            })

    return filtered_tweets


@bot.command()
async def set(ctx, media_type: str = None):
    """Sets the media type preference for .compile and .richcompile."""
    valid_types = ["all", "mp4", "jpg", "png"]
    
    if not media_type or media_type.lower() not in valid_types:
        await ctx.send("Invalid media type. Choose from: `all`, `mp4`, `jpg`, `png`.")
        return

    user_media_preferences[str(ctx.author.id)] = media_type.lower() # Store as string key
    save_user_prefs()
    await ctx.send(f"✅ **Preference set!** Now only fetching `{media_type.upper()}` files for `.compile` and `.richcompile`.")

@bot.command()
async def reload(ctx):
    """Reloads the tweets from the JSON file."""
    load_tweets(force_reload=True)
    await ctx.send(f"✅ **Reloaded!** Currently using profile: `{ACTIVE_PROFILE}` ({len(TWEET_CACHE)} tweets).")

@bot.command()
async def profile(ctx, profile_name: str = None):
    """Switches the active tweet profile (JSON file)."""
    global CURRENT_JSON_PATH, ACTIVE_PROFILE
    
    if not profile_name:
        await ctx.send(f"Current profile: `{ACTIVE_PROFILE}`\nPath: `{CURRENT_JSON_PATH}`\nAvailable profiles: {', '.join(PROFILES.keys())}")
        return

    if profile_name not in PROFILES:
        await ctx.send(f"❌ Profile `{profile_name}` not found. Available: {', '.join(PROFILES.keys())}")
        return

    ACTIVE_PROFILE = profile_name
    CURRENT_JSON_PATH = PROFILES[profile_name]
    load_tweets(force_reload=True)
    await ctx.send(f"✅ Switched to profile `{profile_name}`! Loaded {len(TWEET_CACHE)} tweets.")


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
    filtered_tweets = filter_tweets(ctx, username, year, month, day)

    if not filtered_tweets:
        await ctx.send("No matching media found.")
        return

    total_results = sum(len(tweet["media"]) for tweet in filtered_tweets)
    
    view = MenuView(ctx, filtered_tweets, mode="normal")
    await ctx.send(f"Found **{total_results}** media results. Choose an option:", view=view)

class MenuView(discord.ui.View):
    def __init__(self, ctx, filtered_tweets, mode="normal"):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.filtered_tweets = filtered_tweets
        self.mode = mode
        self.value = None

    @discord.ui.button(label="Slideshow", style=discord.ButtonStyle.primary, emoji="🎞️")
    async def slideshow(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("This isn't your menu!", ephemeral=True)
        
        # Remove buttons immediately
        await interaction.response.edit_message(view=None)
        
        if self.mode == "normal":
            await send_slideshow(self.ctx, self.filtered_tweets)
        else:
            await send_rich_slideshow(self.ctx, self.filtered_tweets)
        self.stop()

    @discord.ui.button(label="All at once", style=discord.ButtonStyle.secondary, emoji="📂")
    async def all_at_once(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("This isn't your menu!", ephemeral=True)

        # Remove buttons immediately
        await interaction.response.edit_message(view=None)

        if self.mode == "normal":
            await send_all(self.ctx, self.filtered_tweets)
        else:
            await send_rich_all(self.ctx, self.filtered_tweets)
        self.stop()

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.danger, emoji="✖️")
    async def exit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("This isn't your menu!", ephemeral=True)
        
        await interaction.response.send_message("Cancelled.", ephemeral=True)
        self.stop()

class PaginationView(discord.ui.View):
    def __init__(self, ctx, data, embed_factory, total_pages):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.data = data
        self.embed_factory = embed_factory
        self.total_pages = total_pages
        self.current_page = 0
        self.message = None

    async def update_view(self, interaction):
        embed = self.embed_factory(self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="<<", style=discord.ButtonStyle.grey)
    async def first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return
        self.current_page = 0
        await self.update_view(interaction)

    @discord.ui.button(label="<", style=discord.ButtonStyle.primary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_view(interaction)

    @discord.ui.button(label=">", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            await self.update_view(interaction)

    @discord.ui.button(label=">>", style=discord.ButtonStyle.grey)
    async def last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return
        self.current_page = self.total_pages - 1
        await self.update_view(interaction)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger)
    async def stop_view(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author: return
        self.stop()
        # Remove buttons but keep the message (freeze state)
        await interaction.response.edit_message(view=None)



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
    """Displays tweets in a slideshow format with button navigation."""
    tweet_count = len(filtered_tweets)

    def generate_embed(index):
        tweet = filtered_tweets[index]
        username_time = f"{tweet['username']}"

        embed = discord.Embed(color=discord.Color.blue())
        if tweet["media"]:
            embed.set_image(url=tweet["media"][0])
        embed.set_footer(text=f"{username_time} ({index + 1}/{tweet_count})")
        return embed

    view = PaginationView(ctx, filtered_tweets, generate_embed, tweet_count)
    view.message = await ctx.send(embed=generate_embed(0), view=view)

@bot.command()
async def richcompile(ctx, *args):
    """Fetch full tweets by username and/or date (year, month, day)."""
    abort_flag[ctx.author.id] = False  

    username, year, month, day = parse_date_filters(args)
    filtered_tweets = filter_tweets(ctx, username, year, month, day)

    if not filtered_tweets:
        await ctx.send("No matching tweets found.")
        return

    await ctx.send(f"Found **{len(filtered_tweets)}** tweets. Choose an option:", view=MenuView(ctx, filtered_tweets, mode="rich"))

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
    """Displays tweets in a rich slideshow format with button navigation."""
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

    view = PaginationView(ctx, filtered_tweets, generate_embed, tweet_count)
    view.message = await ctx.send(embed=generate_embed(0), view=view)


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
    longest_tweet = max(tweets, key=lambda t: len(t.get("tweet_content", "")), default=None)

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

            view = PaginationView(ctx, top_users, generate_embed, total_pages)
            view.message = await ctx.send(embed=generate_embed(0), view=view)
            return

        elif stat_type == "media":
            embed = discord.Embed(title="📊 Media Breakdown", color=discord.Color.blue())
            embed.add_field(name="📸 Images", value=f"{total_images}", inline=True)
            embed.add_field(name="🎥 Videos", value=f"{total_videos}", inline=True)
            await ctx.send(embed=embed)
            return

        elif stat_type == "longest":
            embed = discord.Embed(title="📜 Longest Tweet Liked", description=longest_tweet.get("tweet_content", ""), color=discord.Color.blue())
            embed.set_author(name=longest_tweet["user_handle"], url=f"https://twitter.com/{longest_tweet['user_handle']}/status/{longest_tweet['tweet_id']}")
            embed.set_footer(text=f"Length: {len(longest_tweet.get('tweet_content', ''))} characters")
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

@bot.command(name="help")
async def help_command(ctx):
    """Displays the custom help embed."""
    embed = discord.Embed(title="🤖 TweetFetch Bot Help", description="Here are the available commands:", color=discord.Color.blue())

    # Search Commands
    embed.add_field(
        name="🔎 Search & View",
        value=(
            "`.compile [user] [date]` - Fetch media (slideshow/all).\n"
            "`.richcompile [user] [date]` - Fetch full tweets with text.\n"
            "`.stats [type]` - View stats (`top_users`, `media`, `longest`)."
        ),
        inline=False
    )

    # Settings Commands
    embed.add_field(
        name="⚙️ Settings",
        value=(
            "`.set [type]` - Set media preference (`all`, `mp4`, `jpg`).\n"
            "`.profile [name]` - Switch tweet database profile.\n"
            "`.reload` - Reload tweets from the file."
        ),
        inline=False
    )

    # Misc Commands
    embed.add_field(
        name="🎲 Fun & Misc",
        value=(
            "`.game` - Guess the Tweeter from an image.\n"
            "`.ping` - Check bot latency.\n"
            "`.stop` - Stop the current process."
        ),
        inline=False
    )

    embed.set_footer(text="Use .compile without args to see everything!")
    await ctx.send(embed=embed)

bot.run(TOKEN)
