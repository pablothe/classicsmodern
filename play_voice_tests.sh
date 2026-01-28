#!/bin/bash
# Voice Test Playback Script
# Plays all voice samples with descriptions

echo "🎧 Edge-TTS Voice Comparison"
echo "============================"
echo ""
echo "Playing 6 different voices reading from 'The Call of Cthulhu'"
echo "Each clip is about 1 minute long"
echo ""
read -p "Press Enter to start..."
echo ""

echo "1/6 🇬🇧 SONIA (British Female) - RECOMMENDED for classic literature"
echo "     Clear, professional British accent"
afplay voice_test_sonia_british.mp3
echo ""
sleep 1

echo "2/6 🇺🇸 ARIA (American Female) - Warm and natural"
echo "     Expressive, good for general audiobooks"
afplay voice_test_aria_female.mp3
echo ""
sleep 1

echo "3/6 🇺🇸 GUY (American Male) - Professional narrator"
echo "     Clear, authoritative"
afplay voice_test_guy_male.mp3
echo ""
sleep 1

echo "4/6 🇺🇸 ERIC (American Male Deep) - Commanding presence"
echo "     Deep voice, good for thrillers"
afplay voice_test_eric_deep.mp3
echo ""
sleep 1

echo "5/6 🇬🇧 RYAN (British Male) - Storytelling voice"
echo "     British accent, narrative style"
afplay voice_test_ryan_british.mp3
echo ""
sleep 1

echo "6/6 🇺🇸 JENNY (American Female) - Friendly and conversational"
echo "     Warm, approachable"
afplay voice_test_jenny_friendly.mp3
echo ""

echo "============================"
echo "✓ All voices played!"
echo ""
echo "My recommendation: Sonia (British) for classic literature"
echo ""
echo "To replay individual voices:"
echo "  afplay voice_test_sonia_british.mp3"
echo "  afplay voice_test_aria_female.mp3"
echo "  afplay voice_test_guy_male.mp3"
echo ""
