import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:typed_data';
import 'api_service.dart';

class TranslationService {
  // API key loaded from compile-time env (flutter run --dart-define=SARVAM_API_KEY=...)
  static const String _sarvamApiKey = String.fromEnvironment(
    'SARVAM_API_KEY',
    defaultValue: '',  // Will gracefully fail if not set
  );
  static const String _sarvamBaseUrl = 'https://api.sarvam.ai';
  
  // ✅ Official Sarvam language codes
  static const Map<String, String> supportedLanguages = {
    'English': 'en-IN',
    'Hindi': 'hi-IN', 
    'Tamil': 'ta-IN',
    'Telugu': 'te-IN',
    'Bengali': 'bn-IN',
    'Gujarati': 'gu-IN',
    'Marathi': 'mr-IN',
    'Malayalam': 'ml-IN',
    'Kannada': 'kn-IN',
    'Punjabi': 'pa-IN',
    'Odia': 'or-IN'
  };

  // ✅ FIXED: Direct Sarvam STT API
  static Future<String?> speechToText({
    required Uint8List audioBytes,
    String languageCode = 'hi-IN',
  }) async {
    try {
      print('🎤 Sarvam STT: Converting speech to text...');
      
      var request = http.MultipartRequest(
        'POST', 
        Uri.parse('$_sarvamBaseUrl/speech-to-text') // ✅ Direct to Sarvam
      );
      
      request.headers.addAll({
        'api-subscription-key': _sarvamApiKey,
      });
      
      request.files.add(
        http.MultipartFile.fromBytes(
          'file',
          audioBytes,
          filename: 'audio.wav',
        ),
      );
      
      if (languageCode != 'unknown') {
        request.fields['language_code'] = languageCode;
      }
      
      request.fields['model'] = 'saarika:v2.5';
      
      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);
      
      print('📡 Sarvam STT Status: ${response.statusCode}');
      print('📡 Sarvam STT Response: ${response.body}');
      
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final transcript = data['transcript'] ?? '';
        print('✅ Sarvam STT Success: "$transcript"');
        return transcript;
      } else {
        print('❌ Sarvam STT Error: ${response.statusCode} - ${response.body}');
        return null;
      }
    } catch (e) {
      print('❌ Sarvam STT Exception: $e');
      return null;
    }
  }

  // ✅ FIXED: Direct Sarvam STT+Translation API
  static Future<String?> speechToTextTranslate({
    required Uint8List audioBytes,
  }) async {
    try {
      print('🎤🌐 Sarvam STT+Translate: Converting speech to English...');
      
      var request = http.MultipartRequest(
        'POST', 
        Uri.parse('$_sarvamBaseUrl/speech-to-text-translate') // ✅ Direct to Sarvam
      );
      
      request.headers.addAll({
        'api-subscription-key': _sarvamApiKey,
      });
      
      request.files.add(
        http.MultipartFile.fromBytes(
          'file',
          audioBytes,
          filename: 'audio.wav',
        ),
      );
      
      request.fields['model'] = 'saaras:v2.5';
      
      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);
      
      print('📡 Sarvam STT+Translate Status: ${response.statusCode}');
      print('📡 Sarvam STT+Translate Response: ${response.body}');
      
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final transcript = data['transcript'] ?? '';
        final detectedLang = data['language_code'] ?? 'unknown';
        print('✅ Sarvam STT+Translate: "$transcript" (detected: $detectedLang)');
        return transcript;
      } else {
        print('❌ Sarvam STT+Translate Error: ${response.statusCode} - ${response.body}');
        return null;
      }
    } catch (e) {
      print('❌ Sarvam STT+Translate Exception: $e');
      return null;
    }
  }

  // ✅ FIXED: Direct Sarvam TTS API
  static Future<Uint8List?> textToSpeech({
    required String text,
    String targetLanguageCode = 'hi-IN',
    String speaker = 'meera',
  }) async {
    try {
      print('🔊 Sarvam TTS: Converting text to speech...');
      
      // ✅ Updated speaker mapping for bulbul:v2
      Map<String, String> speakerMap = {
        'en-IN': 'anushka',
        'hi-IN': 'meera',
        'ta-IN': 'anushka',  
        'te-IN': 'anushka',
        'bn-IN': 'anushka',
        'gu-IN': 'anushka',
        'mr-IN': 'anushka',
        'ml-IN': 'anushka',
        'kn-IN': 'anushka',
        'pa-IN': 'anushka',
      };
      
      final response = await http.post(
        Uri.parse('$_sarvamBaseUrl/text-to-speech'), // ✅ Direct to Sarvam
        headers: {
          'api-subscription-key': _sarvamApiKey,
          'Content-Type': 'application/json',
        },
        body: json.encode({
          'inputs': [text.length > 500 ? text.substring(0, 500) : text], // ✅ Use 'inputs' array
          'target_language_code': targetLanguageCode,
          'speaker': speakerMap[targetLanguageCode] ?? 'anushka',
          'pitch': 0.0,
          'pace': 1.0,
          'loudness': 1.0,
          'speech_sample_rate': 22050,
          'enable_preprocessing': true,
          'model': 'bulbul:v2',
        }),
      );

      print('📡 Sarvam TTS Status: ${response.statusCode}');
      
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        if (data['audios'] != null && data['audios'].isNotEmpty) {
          final base64Audio = data['audios'][0];
          final audioBytes = base64Decode(base64Audio);
          print('✅ Sarvam TTS Success: Generated ${audioBytes.length} bytes');
          return audioBytes;
        }
      } else {
        print('❌ Sarvam TTS Error: ${response.statusCode} - ${response.body}');
      }
    } catch (e) {
      print('❌ Sarvam TTS Exception: $e');
    }
    return null;
  }

  // ✅ BACKEND: Translation through your backend (if you have translate endpoint)
  static Future<String> translateText(
    String text, 
    String fromLanguage, 
    String toLanguage
  ) async {
    try {
      print('🔄 Translating: "$text" from $fromLanguage to $toLanguage');
      
      // ✅ Option 1: Direct Sarvam translate (if your backend doesn't have it)
      final response = await http.post(
        Uri.parse('$_sarvamBaseUrl/translate'),
        headers: {
          'api-subscription-key': _sarvamApiKey,
          'Content-Type': 'application/json',
        },
        body: json.encode({
          'input': text,
          'source_language_code': fromLanguage,
          'target_language_code': toLanguage,
        }),
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        String translated = data['translated_text'] ?? text;
        print('✅ Translation successful: "$translated"');
        return translated;
      } else {
        print('❌ Translation error: ${response.statusCode} - ${response.body}');
        return text;
      }
    } catch (e) {
      print('❌ Translation exception: $e');
      return text;
    }
  }

  // ✅ Helper methods
  static Future<String> toEnglish(String text, String fromLanguage) async {
    if (fromLanguage == 'en-IN') return text;
    return await translateText(text, fromLanguage, 'en-IN');
  }

  static Future<String> fromEnglish(String text, String toLanguage) async {
    if (toLanguage == 'en-IN') return text;
    return await translateText(text, 'en-IN', toLanguage);
  }

  static String detectLanguage(String text) {
    if (RegExp(r'[\u0900-\u097F]').hasMatch(text)) return 'hi-IN'; // Hindi
    if (RegExp(r'[\u0B80-\u0BFF]').hasMatch(text)) return 'ta-IN'; // Tamil
    if (RegExp(r'[\u0C00-\u0C7F]').hasMatch(text)) return 'te-IN'; // Telugu
    if (RegExp(r'[\u0980-\u09FF]').hasMatch(text)) return 'bn-IN'; // Bengali
    if (RegExp(r'[\u0A80-\u0AFF]').hasMatch(text)) return 'gu-IN'; // Gujarati
    if (RegExp(r'[\u0900-\u097F]').hasMatch(text)) return 'mr-IN'; // Marathi
    return 'en-IN'; // Default to English
  }
}
