import 'package:firebase_analytics/firebase_analytics.dart';

/// Centralized analytics wrapper.
/// Tracks user actions for product metrics.
class AnalyticsService {
  static final FirebaseAnalytics _analytics = FirebaseAnalytics.instance;

  static FirebaseAnalyticsObserver get observer =>
      FirebaseAnalyticsObserver(analytics: _analytics);

  // --- Auth Events ---
  static Future<void> logLogin(String method) async {
    await _analytics.logLogin(loginMethod: method);
  }

  static Future<void> logSignUp(String method) async {
    await _analytics.logSignUp(signUpMethod: method);
  }

  // --- Chat Events ---
  static Future<void> logChatMessage({
    required String intent,
    required String language,
    bool isVoice = false,
  }) async {
    await _analytics.logEvent(
      name: 'chat_message',
      parameters: {
        'intent': intent,
        'language': language,
        'is_voice': isVoice.toString(),
      },
    );
  }

  static Future<void> logDiseaseDetection({
    required String prediction,
    required bool classifierAvailable,
  }) async {
    await _analytics.logEvent(
      name: 'disease_detection',
      parameters: {
        'prediction': prediction,
        'classifier_available': classifierAvailable.toString(),
      },
    );
  }

  static Future<void> logPriceQuery({
    required String commodity,
    required String district,
  }) async {
    await _analytics.logEvent(
      name: 'price_query',
      parameters: {
        'commodity': commodity,
        'district': district,
      },
    );
  }

  static Future<void> logLanguageChange(String language) async {
    await _analytics.logEvent(
      name: 'language_change',
      parameters: {'language': language},
    );
  }

  static Future<void> logImageUpload() async {
    await _analytics.logEvent(name: 'image_upload');
  }

  static Future<void> logVoiceRecording() async {
    await _analytics.logEvent(name: 'voice_recording');
  }

  // --- Screen Tracking ---
  static Future<void> logScreenView(String screenName) async {
    await _analytics.logScreenView(screenName: screenName);
  }

  // --- User Properties ---
  static Future<void> setUserLanguage(String language) async {
    await _analytics.setUserProperty(name: 'preferred_language', value: language);
  }

  static Future<void> setUserLocation(String location) async {
    await _analytics.setUserProperty(name: 'user_location', value: location);
  }
}
