import discord
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient
import pymongo
import random
import asyncio
import time
import private

bot = commands.Bot(command_prefix="u.")
mongo = AsyncIOMotorClient(private.mongo, retryWrites=False)
bot.db = mongo.unobot

@bot.event
async def on_ready():
	print("Bot is ready")


@bot.command()
async def ping(ctx):
	await ctx.send("Pong!")

def makedeck():
	cards = ["r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9", "r+2", "rskip", "rrev", "g0", "g1", "g2", "g3", "g4", "g5", "g6", "g7", "g8", "g9", "g+2", "gskip", "grev", "b0", "b1", "b2", "b3", "b4", "b5", "b6", "b7", "b8", "b9", "b+2", "bskip", "brev", "y0", "y1", "y2", "y3", "y4", "y5", "y6", "y7", "y8", "y9", "y+2", "yskip", "yrev", "wild", "wild+4"]
	deck = []
	for x in cards:
		if "wild" in x:
			n = 4
			while n>0: n = n-1; deck.append(x)
		elif not x.endswith("0"):
			deck.append(x)
			deck.append(x)
	return deck

def decode(hand, color=False):
	new = []
	n = 1
	for card in hand:
		if card[0].lower() == "r":
			x = f"[{n}] Red {card[1:]}"
			if color:
				return discord.Color.red()
		elif card[0].lower() == "g":
			x = f"[{n}] Green {card[1:]}"
			if color:
				return discord.Color.green()
		elif card[0].lower() == "b":
			if color:
				return discord.Color.blue()
			x = f"[{n}] Blue {card[1:]}"
		elif card[0].lower() == "y":
			x = f"[{n}] Yellow {card[1:]}"
			if color:
				return discord.Color.gold()
		elif card == "wild":
			x = f"[{n}] Wild Card"
		else:
			x = f"[{n}] Wild Card +4"
		n+= 1
		if len(hand) != 1:
			new.append(x)
		else:
			new.append(x[3:])
	return "\n".join(new)
	

@bot.command(alias=["start", "s"])
async def startgame(ctx, *, users):
	try:
		users = users.split()
		players = [ctx.author.id]
		deck = makedeck()
		for user in users:
			if user.startswith("<@") and user.endswith(">"):
				players.append(int(user.lstrip("<@").lstrip("!").lstrip("&").strip(">")))
		await bot.db.games.insert_one({"_id": ctx.author.id})
		await bot.db.games.update_one({"_id": ctx.author.id}, {"$set": {"players": players}})
		#dealing cards
		await ctx.send("Dealing the cards... check your DMs")
		first = random.choice(players)
		for x in players:
			hand = []
			n = 7
			while n>0:
				card = random.choice(deck)
				hand.append(card)
				deck.remove(card)
				n -= 1
			await bot.get_user(x).send(f"Here is your hand: {decode(hand)}")
			await bot.db.games.update_one({"_id": ctx.author.id}, {"$set": {f"{str(x)}.hand": hand}})
			await bot.get_user(x).send(f"The game is starting... {bot.get_user(first)} has the first turn. Pay attention to people's card counts so you can call uno on them.")
		while True:
			currentcard = random.choice(deck)
			if "wild" in currentcard:
				continue
			else:
				deck.remove(currentcard)
				break
		for x in players:
			cardpic = discord.File(f"assets/{currentcard}.png", filename="image.png")
			embed = discord.Embed(color=decode([currentcard], color=True), title="Uno Game Info", description=f"{bot.get_user(first).name}'s turn")
			embed.set_thumbnail(url="attachment://image.png")
			embed.add_field(name="Current Card", value=decode([currentcard]))
			query = await bot.db.games.find_one({"_id": ctx.author.id})
			embed.add_field(name="Your Hand", value=decode(query[str(x)]["hand"]))
			embed.add_field(name=f"{bot.get_user(first).name}'s Hand", value=f"{len(query[str(x)]['hand'])} cards", inline=True)
			embed.add_field(name="Rotation of play", value="Forward", inline=True)
			msg = await bot.get_user(x).send(file=cardpic, embed=embed)
			await bot.db.games.update_one({"_id": ctx.author.id}, {"$set": {"turn": str(first)}})
			await bot.db.games.update_one({"_id": ctx.author.id}, {"$set": {f"{str(x)}.msg": msg.id}})
		await bot.db.games.update_one({"_id": ctx.author.id}, {"$set": {"currentcard": currentcard}})
		await bot.db.games.update_one({"_id": ctx.author.id}, {"$set": {"rotation": "forward"}})
		await bot.db.games.update_one({"_id": ctx.author.id}, {"$set": {"deck": deck}})
		await turn(ctx.author.id, first)
	except pymongo.errors.DuplicateKeyError:
		await ctx.send("You already have a game going. Would you like to delete it and start a new one? [Y/N]")
		try:
			msg = await bot.wait_for("message", check=lambda m: m.author == ctx.author and m.content.lower() in ["y", "n", "yes", "no"], timeout=10)
			if msg.content.lower() == "y" or msg.content.lower() == "yes":
				await deletegame(ctx)
				await startgame(ctx, users)
			else:
				await ctx.send("You cannot start a new game until you delete your current game. Please run u.startgame again or run u.deletegame to manually delete your game")
		except asyncio.TimeoutError:
			await ctx.send("You didn't answer the question so I did not delete your game. You can run u.startgame again or run u.deletegame to manually delete your game")


async def turn(id, player):
	data = await bot.db.games.find_one({"_id": id})
	player = bot.get_user(player)
	notif = await player.send("It is your turn! To play a card enter the number to the left of the card. To draw a card type 'draw', if you only have 2 cards left and you play one remember to type 'uno'")
	action = await bot.wait_for("message", check=lambda m: m.author.id == player.id)
	if action.content.isdigit():
		card = data[str(player.id)]["hand"][int(action.content) - 1]
		if card[0] == data["currentcard"][0].lower() or card[1:] == data["currentcard"][1:]:
			await bot.db.games.update_one({"_id": id}, {"$set": {"currentcard": card}})
			hand = data[str(player.id)]["hand"]
			hand.remove(card)
			await bot.db.games.update_one({"_id": id}, {"$set": {f"{str(player.id)}.hand": hand}})
			if card[1:] == "skip":
				if data["players"].index(player.id) + 1 == len(data["players"]):
					skipped = 0
				else:
					skipped = data["players"].index(player.id) + 1
				skipped = data["players"][skipped]
				await notif.delete()
				await asyncio.gather(uno_check(id, player))
				await update_embeds(id, player, f"{player.name} played a {decode([card])} on {bot.get_user(skipped).name}", skip=True)
			elif card[1:] == "rev":
				if data["rotation"] == "forward":
					await bot.db.games.update_one({"_id": id}, {"$set": {"rotation": "reverse"}})
					move = f"{player.name} played a {decode([card])} and changed the rotation to reverse"
				else:
					await bot.db.games.update_one({"_id": id}, {"$set": {"rotation": "forward"}})
					move = f"{player.name} played a {decode([card])} and changed the rotation to forward"
					await notif.delete()
				await asyncio.gather(uno_check(id, player))
				await update_embeds(id, player, move)
			elif card[1:] == "+2":
				if data["players"].index(player.id) + 1 == len(data["players"]):
					victim = 0
				else:
					victim = data["players"].index(player.id) + 1
				victim = data["players"][victim]
				await draw(id, victim, 2)
				await notif.delete()
				await asyncio.gather(uno_check(id, player))
				await update_embeds(id, player, f"{player.name} played a {decode([card])} on {bot.get_user(victim).name}", skip=True)
			else:
				move = f"{player.name} played a {decode([card])}"
				await notif.delete()
				await asyncio.gather(uno_check(id, player))
				await update_embeds(id, player, move)
		elif "wild" in card:
			await player.send("You played a wild. Please type one of the four colors to change to.")
			choice = await bot.wait_for("message", check=lambda m: m.author.id == player.id and m.content.lower() in ["blue", "red", "green", "yellow"])
			if "wild+4" in card:
				colors = {"blue": "Blue Wild +4", "red": "Red Wild +4", "yellow": "Yellow Wild +4", "green": "Green Wild +4"}
			else:
				colors = {"blue": "Blue Wild", "red": "Red Wild", "yellow": "Yellow Wild", "green": "Green Wild"}
			hand = data[str(player.id)]["hand"]
			hand.remove(card)
			await bot.db.games.update_one({"_id": id}, {"$set": {f"{str(player.id)}.hand": hand}})
			await bot.db.games.update_one({"_id": id}, {"$set": {"currentcard": colors[choice.content]}})
			if card == "wild+4":
				if data["players"].index(player.id) + 1 == len(data["players"]):
					victim = 0
				else:
					victim = data["players"].index(player.id) + 1
				victim = data["players"][victim]
				await draw(id, victim, 4)
				await asyncio.gather(uno_check(id, player))
				await update_embeds(id, player, f"{player.name} used a wild +4 on {bot.get_user(victim).name} and changed the color to {choice.content}", skip=True)
			else:
				await asyncio.gather(uno_check(id, player))
				await update_embeds(id, player, f"{player.name} used a wild and changed the color to {choice.content}")
		else:
			await player.send("The card you play must match the current card in either color or numeric value. Please try again.")
			await notif.delete()
			await turn(id, player.id)
	elif action.content.lower() == "draw":
		await draw(id, player.id)
		await notif.delete()
		await update_embeds(id, player, f"{player.name} drew a card.")
	else:
		await player.send("Invalid move! Please try again.")
		await notif.delete()
		await turn(id, player.id)

async def draw(id, player, num=1):
	data = await bot.db.games.find_one({"_id": id})
	while num>0:
		deck = data["deck"]
		card = random.choice(deck)
		deck.remove(card)
		hand = data[str(player)]["hand"]
		hand.append(card)
		num -= 1
	await bot.db.games.update_one({"_id": id}, {"$set": {"deck": deck}})
	await bot.db.games.update_one({"_id": id}, {"$set": {f"{str(player)}.hand": hand}})

async def uno_check(id, player):
	data = await bot.db.games.find_one({"_id": id})
	if len(data[str(player.id)]["hand"]) == 1:
		try:
			uno = await bot.wait_for("message", check=lambda m: m.author.id != 714954865947705426 and m.content.lower() == "uno", timeout=15)
			if uno.author.id != player.id:
				await draw(id, player.id, 2)
				for x in data["players"]:
					await bot.get_user(x).send(f"{player.name} forgot to say Uno. They will be given 2 more cards")
			else:
				for x in data["players"]:
					await bot.get_user(x).send(f"{player.name} said Uno before anybody else so they gain no penalty")
		except asyncio.TimeoutError:
			for x in data["players"]:
				await bot.get_user(x).send(f"Everyone waited too long to call uno on {player.name} so they got away with it. Pay attention next time")

async def update_embeds(id, play, action, next=True, skip=False):
	data = await bot.db.games.find_one({"_id": id})
	for player in data["players"]:
		player = bot.get_user(int(player))
		if next==True:
			if not skip:
				if data["players"].index(play.id) + 1 == len(data["players"]):
					currentplayer = 0
				else:
					currentplayer = data["players"].index(play.id) + 1
			else:
				if len(data["players"]) > 2:
					if data["players"].index(play.id) + 2 >= len(data["players"]):
							currentplayer = 1
					else:
						currentplayer = data["players"].index(play.id) + 2
				else:
					currentplayer = data["players"].index(play.id)
		else:
			currentplayer = data["players"].index(play.id)
		if data["rotation"] == "forward":
			if len(data["players"]) - 1 == currentplayer:
				nextplayer=0
			else:
				nextplayer = currentplayer + 1
		else:
			if currentplayer == 0:
				nextplayer = len(data["players"]) - 1
			else:
				nextplayer = currentplayer - 1
		if "Wild" in data["currentcard"]:
			if "Wild +4" in data["currentcard"]:
				cardpic = discord.File(f"assets/wild+4.png", filename="image.png")
			else:
				cardpic = discord.File(f"assets/wild.png", filename="image.png")
			currentcard = data["currentcard"]
		else:
			cardpic = discord.File(f"assets/{data['currentcard']}.png", filename="image.png")
			currentcard = decode([data["currentcard"]])
		currentplayer = bot.get_user(data['players'][currentplayer])
		nextplayer = bot.get_user(data["players"][nextplayer])
		embed = discord.Embed(title="Uno Game Info", description=f"{action}\n{currentplayer.name}'s turn\n{nextplayer.name}'s turn is next", color=decode([data["currentcard"]], color=True))
		embed.set_thumbnail(url="attachment://image.png")
		embed.add_field(name="Current Card", value=currentcard)
		embed.add_field(name="Your Hand", value=decode(data[str(player.id)]["hand"]))
		embed.add_field(name=f"{bot.get_user(int(data['turn'])).name}'s Hand", value=f"{len(data[str(currentplayer.id)]['hand'])} cards", inline=True)
		embed.add_field(name="Rotation of play", value=data["rotation"], inline=True)
		msg = await player.fetch_message(int(data[str(player.id)]["msg"]))
		await msg.delete()
		await asyncio.sleep(1.5)
		msg = await player.send(file=cardpic, embed=embed)
		await bot.db.games.update_one({"_id": id}, {"$set": {f"{str(player.id)}.msg": msg.id}})
	if next==True:
		await turn(id, currentplayer.id)


@bot.command()
async def deletegame(ctx):
	await bot.db.games.delete_one({"_id": ctx.author.id})
	await ctx.send("Your UNO game was deleted")

			
@bot.command()
@commands.is_owner()
async def kill(ctx):
	"Forcefully kill the bot"
	await ctx.send("Killing the bot...")
	print("Bot was killed.")
	await bot.close()

bot.run(private.token)