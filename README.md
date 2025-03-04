# Twitter Media Fetch Bot

## Overview
Twitter Media Fetch Bot is a **Discord bot** that allows users to retrieve and display **liked tweets with media** from a local JSON file. The bot supports **filtering by username, date, and keywords**, and it properly embeds **JPG, PNG, and MP4 files**.

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

---

### `.richcompile [username] [year] [month] [day]`
**Retrieve full tweets with media.**  
Includes **tweet text, timestamp, and media** in an organized format.

**Syntax Examples:**  
```
.richcompile
```
> Returns **all liked tweets with full details**.

---

### `.stop`
**Stops any ongoing `.compile` or `.richcompile` command.**  

---

## **Installation & Setup**
### **1. Clone the Repository**
```
git clone https://github.com/YOUR-USERNAME/YOUR-REPO.git
cd YOUR-REPO
```

### **2. Install Dependencies**
Ensure you have Python installed, then run:
```
pip install discord.py
```

### **3. Configure the Bot**
1. **Create a `config.json` file** (this is ignored by Git).
2. **Copy `configtemplate.json`** and rename it to `config.json`.
3. **Edit `config.json`** and add your bot token:


### **4. Run the Bot**
```
python bot.py
```
---
