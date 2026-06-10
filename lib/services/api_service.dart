import 'package:http/http.dart' as http;
import 'dart:convert';

class ApiService {
  // Backend URL — configurable via environment, defaults to localhost for development.
  // For Android emulator use 10.0.2.2, for physical device use your machine's LAN IP.
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000/api', // Android emulator default
  );

  /// Start a new chat session. Returns {ok, session_id, message}.
  static Future<Map<String, dynamic>> startChatSession() async {
    final url = Uri.parse('$baseUrl/chat/start-session');

    try {
      final response = await http.post(
        url,
        headers: {'Content-Type': 'application/json'},
        body: json.encode({}),
      );

      if (response.statusCode == 200) {
        return json.decode(response.body);
      } else {
        return {'ok': false, 'error': 'Failed to create session: ${response.statusCode}'};
      }
    } catch (e) {
      return {'ok': false, 'error': 'Network error: $e'};
    }
  }

  /// Send a message to the RAG-augmented chat endpoint.
  /// [location] is optional: {'state': 'UP', 'district': 'Lucknow'}
  /// [language] is optional: e.g. 'en', 'hi', 'bn'
  static Future<Map<String, dynamic>> sendChatMessage(
    String message, {
    String? sessionId,
    Map<String, dynamic>? sessionState,
    Map<String, String>? location,
    String? language,
  }) async {
    final url = Uri.parse('$baseUrl/chat/message');

    try {
      final payload = <String, dynamic>{
        'message': message,
        'session_id': sessionId,
        'session_state': sessionState ?? {},
      };

      // Attach location for region-specific RAG results
      if (location != null && location.isNotEmpty) {
        payload['location'] = location;
      }

      // Attach language preference
      if (language != null && language.isNotEmpty) {
        payload['language'] = language;
      }

      final response = await http.post(
        url,
        headers: {'Content-Type': 'application/json'},
        body: json.encode(payload),
      );

      if (response.statusCode == 200) {
        return json.decode(response.body);
      } else {
        throw Exception('Chat error: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Network error: $e');
    }
  }

  // Classify text as price_enquiry or non_price_enquiry
  static Future<Map<String, dynamic>> classifyText(String text) async {
    final url = Uri.parse('$baseUrl/classify');
    
    try {
      final response = await http.post(
        url,
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'text': text}),
      );

      if (response.statusCode == 200) {
        return json.decode(response.body);
      } else {
        throw Exception('Failed to classify text. Status: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Network error: $e');
    }
  }

  // Multi-turn chat for price enquiries with slot filling
  static Future<Map<String, dynamic>> chatWithSlots(
    String message, 
    Map<String, dynamic> sessionState
  ) async {
    final url = Uri.parse('$baseUrl/chat/slots');
    
    try {
      final response = await http.post(
        url,
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'message': message,
          'session_state': sessionState,
        }),
      );

      if (response.statusCode == 200) {
        return json.decode(response.body);
      } else {
        throw Exception('Failed to get chat response. Status: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Network error: $e');
    }
  }

  // Predict crop disease from uploaded image
  static Future<Map<String, dynamic>> predictDisease(String imagePath) async {
    final url = Uri.parse('$baseUrl/disease/predict');
    
    try {
      var request = http.MultipartRequest('POST', url);
      request.files.add(await http.MultipartFile.fromPath('file', imagePath));
      
      var streamedResponse = await request.send();
      var response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        return json.decode(response.body);
      } else {
        throw Exception('Failed to predict disease. Status: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Network error: $e');
    }
  }

  // ✅ NEW: Continue conversation about a detected disease with Gemini AI
  static Future<Map<String, dynamic>> sendDiseaseChat(
    String message, 
    String diseaseContext
  ) async {
    final url = Uri.parse('$baseUrl/disease/chat');
    
    try {
      final response = await http.post(
        url,
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'message': message,
          'disease_context': diseaseContext,
        }),
      );

      if (response.statusCode == 200) {
        return json.decode(response.body);
      } else {
        throw Exception('Failed to send disease chat. Status: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Network error: $e');
    }
  }

  // ✅ NEW: Get disease chat history
  static Future<Map<String, dynamic>> getDiseaseeChatHistory() async {
    final url = Uri.parse('$baseUrl/disease/chat/history');
    
    try {
      final response = await http.get(url);

      if (response.statusCode == 200) {
        return json.decode(response.body);
      } else {
        throw Exception('Failed to get chat history. Status: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Network error: $e');
    }
  }

  // ✅ NEW: Clear disease chat history
  static Future<Map<String, dynamic>> clearDiseaseeChatHistory() async {
    final url = Uri.parse('$baseUrl/disease/chat/clear');
    
    try {
      final response = await http.post(
        url,
        headers: {'Content-Type': 'application/json'},
        body: json.encode({}),
      );

      if (response.statusCode == 200) {
        return json.decode(response.body);
      } else {
        throw Exception('Failed to clear chat history. Status: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Network error: $e');
    }
  }

  // Health check
  static Future<Map<String, dynamic>> healthCheck() async {
    final url = Uri.parse('$baseUrl/health');
    
    try {
      final response = await http.get(url);

      if (response.statusCode == 200) {
        return json.decode(response.body);
      } else {
        throw Exception('Health check failed. Status: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Network error: $e');
    }
  }

  // ✅ NEW: Get API information and available endpoints
  static Future<Map<String, dynamic>> getApiInfo() async {
    final url = Uri.parse('$baseUrl/info');
    
    try {
      final response = await http.get(url);

      if (response.statusCode == 200) {
        return json.decode(response.body);
      } else {
        throw Exception('Failed to get API info. Status: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Network error: $e');
    }
  }
}
