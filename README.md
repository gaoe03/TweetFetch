# TweetFetch
## Overview
TweetFetch is a **Discord bot** that allows users to retrieve and display **liked tweets with media** from a local JSON file. The bot supports **filtering by username, date, and keywords**, and it properly embeds **JPG, PNG, and MP4 files**. Additionally, it features a **game mode**, **button-based navigation**, **profile switching**, and **detailed stats tracking**.

---

## **Commands & Syntax**

### `.ping`
**Check if the bot is running and view response time.**  
```
.ping
```
**Example Output:**  
```
Pong! 102ms
```

---

### `.compile [username] [year] [month] [day]`
**Retrieve media from liked tweets.**  
If no parameters are provided, it fetches all liked tweets with media.

**Syntax Examples:**  
```
.compile
```
> Returns **all liked tweets** with media.

```
.compile username
```
> Returns all **liked tweets from the specified user**.

```
.compile 2025
```
> Returns **all tweets liked in 2025**.

```
.compile username 2024 january 5
```
> Returns **tweets liked from username on January 5, 2024**.

**Display Options:**
- **Slideshow** (use buttons to navigate)
- **All at once**
- **Exit**

---

### `.richcompile [username] [year] [month] [day]`
**Retrieve full tweets with media and text.**  
Includes **tweet text, timestamp, and media** in an organized format.

**Syntax Examples:**  
```
.richcompile
```
> Returns **all liked tweets with full details**.

```
.richcompile username 2025
```
> Returns **all liked tweets from username in 2025**.

**Display Options:**
- **Slideshow** (use buttons to navigate)
- **All at once**
- **Exit**

---

### `.set [type]`
**Set media type preference for compile commands.**  
Valid types: `all`, `mp4`, `jpg`, `png`

```
.set mp4
```
> Only fetch MP4 files in future `.compile` and `.richcompile` commands.

---

### `.profile [name]`
**Switch between different tweet profiles.**  

```
.profile
```
> View current profile and available profiles.

```
.profile profile2
```
> Switch to a different profile.

---

### `.reload`
**Reload tweets from the JSON file.**  
Useful after updating the JSON file without restarting the bot.

```
.reload
```

---

### `.stop`
**Stops any ongoing `.compile`, `.richcompile`, or `.game` command.**  
```
.stop
```
---

### `.stats [category]`
**View statistics about liked tweets.**

**Categories:**
- `.stats` - **General stats** (total tweets, media breakdown, most liked users)
- `.stats top_users` - **Paginated list of most liked users** (use buttons to navigate)
- `.stats media` - **Breakdown of images & videos**
- `.stats longest` - **Longest liked tweet**

---

### `.game`
**Guess the Tweeter from a liked tweet image.**  
- The bot sends a random image from liked tweets.
- **User has 30 seconds to guess the username.**
- **Hints given at 15s & 24s** (partial username or like count).
- **Reacting with the shrug emoji stops the game and reveals the answer.**

```
.game
```

---
