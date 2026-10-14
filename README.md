# tango

## 1. Core Flashcard Experience
- Shuffle vocabulary and show only the Japanese word; swipe left to reveal answers and mark missed, swipe right to mark remembered.
- Display reading, meaning, example sentence, and translation; track progress and show a session summary.

## 2. Review Rounds
- Repeat missed words in subsequent rounds until remembered, with an option to finish review early.
- Summarize unique words practised, first-round accuracy, and words corrected; refreshing resets the session.

## 3. Add Vocabulary
- Add words through the website and use AI to generate readings, meanings, example sentences, and translations.
- Validate entries, prevent duplicates, sort by Japanese reading (五十音順), and commit updates to GitHub JSON.

## 4. Hosting and Infrastructure
- Use Python Flask to serve the frontend and backend from one Azure App Service Web App on the Free tier.
- Store vocabulary in a private GitHub repository; manage Azure resources with Bicep and keep API keys server-side.

## 5. Future Feature: Study Reminders
- Later, make the app installable as a PWA and send web push notifications when daily study is missed.
- Track the last study date and schedule reminders; exclude this from the initial build.