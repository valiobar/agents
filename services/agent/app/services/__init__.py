"""Service package.

Keep this package initializer side-effect free. Eagerly importing every service
creates circular imports between the chat runtime and tool context.
"""
