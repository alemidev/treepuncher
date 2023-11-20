# treepuncher
An hackable headless Minecraft client, built with [aiocraft](https://git.alemi.dev/aiocraft/about)

### Features
 * persistent storage
 * configuration file
 * pluggable plugin system
 * event system with callbacks
 * world processing

## Quick Start
Treepuncher is still in development and thus not available yet on PyPI, to install it fetch directly from git:
 * `pip install "git+https://git.alemi.dev/treepuncher@v0.3.0"`

Treepuncher can both be run as a pluggable CLI application or as a library, depending on how much you need to customize its behavior

### as an application
Treepuncher ships as a standalone CLI application which you can run with `python -m treepuncher`
 * create your first addon (a simple chat logger) inside `./addons/chat_logger.py`
```py
from dataclasses import dataclass
from treepuncher import Addon, ConfigObject
from treepuncher.events import ChatEvent

class ChatLogger(Addon):
	@dataclass
	class Options(ConfigObject):
		prefix : str = ""
	config : Options

	def register(self):
		@self.client.on(ChatEvent)
		async def print_chat(event: ChatEvent):
			print(f"{event.user} >> {event.text})
```
 * create a config file: `my_bot.ini`
```ini
[Treepuncher]
server = your.server.com
username = your_account_username
client_id = your_microsoft_authenticator_client_id
client_secret = your_microsoft_authenticator_client_secret
code = microsoft_auth_code

[ChatLogger]
prefix = CHAT |::
```
 * run the treepuncher client : `python -m treepuncher my_bot`

### as a library
 * instantiate the Treepuncher object
```py
from treepuncher import Treepuncher

client = Treepuncher(
	"my_bot",
	server="your.server.com",
)
```
 * prepare your addons (must extend `treepuncher.Addon`) and install them
```py
from treepuncher import Addon

class MyAddon(Addon):
	pass

addon = MyAddon()
client.install(addon)
```
 * run your client
```py
client.run()
```

## Authentication
Treepuncher supports both legacy Yggdrasil authentication (with options to override session and auth server) and modern Microsoft OAuth authentication. It will store the auth token inside a session file, to be able to restart without requiring credentials again.

To be able to use Microsoft authentication you will need to register an Azure application (see [community](https://wiki.vg/Microsoft_Authentication_Scheme) and [microsoft](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app) docs on how to do that).

This is a tedious process but can be done just once for many accounts, sadly Microsoft decided that only kids play minecraft and we developers should just suffer...

**Be warned that Microsoft may limit your account if they find your activity suspicious**

Once you have your `client_id` and `client_secret` use [this page](https://fantabos.co/msauth) to generate a login code: put in your `client_id` and any state and press `auth`.
You will be brought to Microsoft login page, input your credentials, authorize your application and you will be redirected back to the `msauth` page, but now there should be a code in the `auth code` field.

Put this code in your config and you're good to go!

If you'd rather use classic Yggdrasil authentication, consider [ftbsc yggdrasil](https://yggdrasil.fantabos.co) ([src](https://git.fantabos.co/yggdrasil))

Legacy Yggdrasil authentication supports both an hardcoded password or a pre-authorized access token


## Contributing
Development is managed by [ftbsc](https://fantabos.co), mostly on [our git](https://git.fantabos.co). If you'd like to contribute, get in contact with any of us using any available form.

