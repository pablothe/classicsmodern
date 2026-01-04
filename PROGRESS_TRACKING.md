# Progress Tracking Guide

## How Progress Tracking Works

### Web Player (Automatic)
The web player tracks your progress automatically:

✅ **What's Tracked:**
- Current chapter/part number (1-25)
- Exact timestamp within that part
- Playback speed preference
- Last played date/time

✅ **When It Saves:**
- Every 10 seconds while playing
- When you skip forward/back
- When you switch parts
- When you close the browser

✅ **Where It's Stored:**
- Browser localStorage (local to your computer)
- Persists across browser restarts
- Unique per audiobook directory

### View Your Progress

**In the Web Player:**
1. Open http://localhost:8000/player.html
2. Progress bar shows current position
3. Current part is highlighted in playlist
4. Time display shows: `Current / Total`

**In Browser Console:**
```javascript
// See saved progress
localStorage.getItem('audiobook_track')  // Current part number
localStorage.getItem('audiobook_time')   // Current timestamp
```

### Manual Progress Management

**Export Progress:**
```javascript
// In browser console
const progress = {
    track: localStorage.getItem('audiobook_track'),
    time: localStorage.getItem('audiobook_time'),
    book: 'Crime and Punishment Chapter 1',
    date: new Date().toISOString()
};
console.log(JSON.stringify(progress));
// Copy and save this JSON somewhere
```

**Import Progress:**
```javascript
// In browser console
const progress = {
    track: '5',
    time: '123.45'
};
localStorage.setItem('audiobook_track', progress.track);
localStorage.setItem('audiobook_time', progress.time);
location.reload();  // Reload to apply
```

### Cross-Device Progress (Manual)

**Current State:**
- Progress is saved per browser
- Doesn't sync between devices automatically

**Workaround for Multi-Device:**

1. **Export from Device A:**
   - Open browser console
   - Run: `console.log('Part:', localStorage.getItem('audiobook_track'), 'Time:', localStorage.getItem('audiobook_time'))`
   - Note the numbers

2. **Import to Device B:**
   - Open browser console
   - Run: `localStorage.setItem('audiobook_track', 'X'); localStorage.setItem('audiobook_time', 'Y')`
   - Replace X and Y with your numbers
   - Reload page

**Future Enhancement:**
- Add export/import buttons to UI
- QR code generation for easy transfer
- Cloud sync (optional)

---

## Combined File Progress

### Issue with Combined Files
When you combine all parts into a single MP3:
- ❌ Lose chapter markers
- ❌ Can't track which "part" you're on
- ⚠️ Progress depends on your audio player

### Solutions:

**Option 1: Add Chapter Markers** (Advanced)
```bash
# Install mp3chaps (for adding chapter markers)
brew install mp3chaps

# Create chapters file
cat > chapters.txt << EOF
00:00:00 Part 1
00:03:15 Part 2
00:06:30 Part 3
# ... etc
EOF

# Add chapters to MP3
mp3chaps -i combined.mp3
```

**Option 2: Use Player with Bookmarks**
- VLC: Playback → Custom Bookmarks
- Audacity: Add labels
- iTunes: Remember position (automatic)

**Option 3: Keep Playlist + Combined**
- Use playlist for fine-grained control
- Use combined file for mobile/sharing
- Maintain progress in web player

---

## Best Practices

### For Maximum Control
1. ✅ Use **web player** as primary
2. ✅ Keep **separate parts** available
3. ✅ Create **combined file** for mobile
4. ✅ Note progress before switching devices

### Progress Backup
```bash
# Create progress snapshot (manual)
echo "$(date): Part $(localStorage.getItem('audiobook_track')), Time $(localStorage.getItem('audiobook_time'))" >> audiobook_progress.log
```

### Multiple Audiobooks
Each audiobook should be in its own directory:
```
books/
├── crime_punishment_ch1/audio/   # Progress tracked separately
├── crime_punishment_ch2/audio/   # Progress tracked separately
└── alice_wonderland/audio/       # Progress tracked separately
```

The web player uses the directory path to separate progress.

---

## Future Features (Roadmap)

### Phase 1 (Easy Additions)
- [ ] Visual progress percentage in UI
- [ ] "Mark as completed" button
- [ ] Export/import progress buttons
- [ ] Multiple playback bookmarks

### Phase 2 (Medium Complexity)
- [ ] Progress history/statistics
- [ ] Listening time analytics
- [ ] Resume from multiple checkpoints
- [ ] Notes/annotations

### Phase 3 (Mobile App)
- [ ] Cloud sync across devices
- [ ] Auto-save to cloud
- [ ] Offline progress sync
- [ ] Family sharing

---

## Troubleshooting

### Progress Not Saving
```javascript
// Check if localStorage works
localStorage.setItem('test', 'hello');
console.log(localStorage.getItem('test'));  // Should print 'hello'
```

If it doesn't work:
- Check browser privacy settings
- Disable private/incognito mode
- Try different browser

### Progress Reset After Browser Clear
- Browser cache clear removes localStorage
- **Solution**: Export progress regularly
- Use dedicated profile for audiobooks

### Can't Resume on Different Computer
- localStorage is per-browser, per-computer
- **Solution**: Note progress manually or wait for cloud sync feature

---

## Quick Commands

```bash
# Start web player (auto progress tracking)
python serve_audiobook.py books/crime_punishment/chunks/test_chunk/translated/audio/

# View progress (in browser console after opening player)
localStorage.getItem('audiobook_track')  # Current part
localStorage.getItem('audiobook_time')   # Current time

# Reset progress (if needed)
localStorage.removeItem('audiobook_track')
localStorage.removeItem('audiobook_time')
```

---

## Summary

✅ **Progress tracking is already built-in** to the web player
✅ **Saves automatically** every 10 seconds
✅ **Resumes automatically** when you reopen
✅ **Per-audiobook** tracking (different books = different progress)
✅ **Browser-based** (no server/cloud needed)

For the best experience:
1. Use the web player for listening
2. Keep separate audio parts (don't delete them)
3. Create combined file only for mobile/sharing
4. Export progress manually if switching devices
