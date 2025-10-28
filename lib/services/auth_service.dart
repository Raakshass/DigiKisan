import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

class AuthService {
  static const String baseUrl = 'http://10.61.89.244:8000/api';
  static String? _token;
  static Map<String, dynamic>? _userInfo;

  // Get current token
  static String? get token => _token;
  static Map<String, dynamic>? get userInfo => _userInfo;

  // Store token and user info after login/register
  static Future<void> storeAuthData(String token, Map<String, dynamic> userInfo) async {
    _token = token;
    _userInfo = userInfo;
    
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('auth_token', token);
    await prefs.setString('user_info', json.encode(userInfo));
  }

  // Load token from storage
  static Future<bool> loadAuthData() async {
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString('auth_token');
    final userInfoString = prefs.getString('user_info');
    
    if (_token != null && userInfoString != null) {
      _userInfo = json.decode(userInfoString);
      return true;
    }
    return false;
  }

  // Clear auth data (logout)
  static Future<void> clearAuthData() async {
    _token = null;
    _userInfo = null;
    
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('auth_token');
    await prefs.remove('user_info');
  }

  // Send authenticated chat message
  static Future<Map<String, dynamic>?> sendChatMessage(String message) async {
    if (_token == null) return null;

    try {
      final response = await http.post(
        Uri.parse('$baseUrl/chat/send'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $_token',
        },
        body: json.encode({'message': message}),
      );

      if (response.statusCode == 200) {
        return json.decode(response.body);
      }
    } catch (e) {
      print('Chat error: $e');
    }
    return null;
  }
}
