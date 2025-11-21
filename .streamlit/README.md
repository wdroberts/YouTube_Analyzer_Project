# Streamlit Configuration

## Theme Settings

This folder contains Streamlit configuration files for the YouTube Analyzer application.

### Current Theme: Dark Mode (YouTube-inspired)

The app is configured with a dark theme by default:
- **Background**: Dark gray (#181818) - matches YouTube's dark mode
- **Accent Color**: YouTube red (#FF0000)
- **Text**: White for high contrast
- **Cards/Sidebar**: Slightly lighter gray (#212121)

### Switching Themes

#### Method 1: User Toggle (In-App)
Users can switch themes anytime:
1. Click hamburger menu (⋮) in top-right
2. Go to **Settings**
3. Choose **Light** or **Dark** theme

#### Method 2: Change Default Theme
To make light mode the default:
```bash
# Backup current dark config
mv config.toml config.dark.toml

# Use light config
mv config.light.toml config.toml

# Restart app
```

To switch back to dark:
```bash
mv config.toml config.light.toml
mv config.dark.toml config.toml
```

### Files

- **`config.toml`** - Active configuration (currently dark theme)
- **`config.light.toml`** - Light theme alternative
- **`README.md`** - This file

### Theme Colors

#### Dark Theme (Active)
```toml
primaryColor = "#FF0000"           # YouTube red
backgroundColor = "#181818"        # Dark gray
secondaryBackgroundColor = "#212121"
textColor = "#FFFFFF"              # White
```

#### Light Theme (Alternative)
```toml
primaryColor = "#FF0000"           # YouTube red
backgroundColor = "#FFFFFF"        # White
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"              # Dark gray
```

### Server Settings

The configuration also includes:
- Max upload size: 50MB (matches document limit)
- XSRF protection enabled
- Headless mode enabled
- Usage stats disabled

### Customization

To customize the theme, edit `config.toml`:

```toml
[theme]
primaryColor = "#YOUR_COLOR"    # Button and accent color
backgroundColor = "#YOUR_COLOR"  # Main background
textColor = "#YOUR_COLOR"       # Text color
```

Then restart the app to see changes.

### More Information

- [Streamlit Theme Documentation](https://docs.streamlit.io/library/advanced-features/theming)
- [Streamlit Configuration](https://docs.streamlit.io/library/advanced-features/configuration)

