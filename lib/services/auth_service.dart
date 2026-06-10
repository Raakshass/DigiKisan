import 'package:firebase_auth/firebase_auth.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Firebase-based authentication service.
/// Handles sign-up, login, logout, and persists location metadata locally.
class AuthService {
  static final FirebaseAuth _auth = FirebaseAuth.instance;

  // Cached location data
  static String? _userState;
  static String? _userDistrict;

  // --- Getters ---
  static User? get currentUser => _auth.currentUser;
  static bool get isLoggedIn => _auth.currentUser != null;
  static String? get token => null; // Firebase handles tokens internally
  static String? get userState => _userState;
  static String? get userDistrict => _userDistrict;

  /// User info map for backward compatibility.
  static Map<String, dynamic>? get userInfo {
    final user = _auth.currentUser;
    if (user == null) return null;
    return {
      'uid': user.uid,
      'email': user.email ?? '',
      'displayName': user.displayName ?? '',
      'photoURL': user.photoURL ?? '',
    };
  }

  /// Returns the location map for API calls, or null if not set.
  static Map<String, String>? get locationPayload {
    if (_userState == null && _userDistrict == null) return null;
    final map = <String, String>{};
    if (_userState != null) map['state'] = _userState!;
    if (_userDistrict != null) map['district'] = _userDistrict!;
    return map;
  }

  // --- Auth Methods ---

  /// Register with email and password.
  /// Returns null on success, error message on failure.
  static Future<String?> register({
    required String email,
    required String password,
    String? fullName,
    String? location,
  }) async {
    try {
      final cred = await _auth.createUserWithEmailAndPassword(
        email: email,
        password: password,
      );

      // Set display name if provided
      if (fullName != null && fullName.isNotEmpty) {
        await cred.user?.updateDisplayName(fullName);
      }

      // Parse and store location
      if (location != null && location.isNotEmpty) {
        await _parseAndStoreLocation(location);
      }

      return null; // success
    } on FirebaseAuthException catch (e) {
      return _mapAuthError(e.code);
    } catch (e) {
      return 'Registration failed: $e';
    }
  }

  /// Login with email and password.
  /// Returns null on success, error message on failure.
  static Future<String?> login({
    required String email,
    required String password,
  }) async {
    try {
      await _auth.signInWithEmailAndPassword(
        email: email,
        password: password,
      );
      // Restore saved location
      await _loadLocation();
      return null; // success
    } on FirebaseAuthException catch (e) {
      return _mapAuthError(e.code);
    } catch (e) {
      return 'Login failed: $e';
    }
  }

  /// Get Firebase ID token for backend API calls.
  static Future<String?> getIdToken() async {
    return await _auth.currentUser?.getIdToken();
  }

  /// Logout.
  static Future<void> logout() async {
    await _auth.signOut();
    _userState = null;
    _userDistrict = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('user_state');
    await prefs.remove('user_district');
  }

  // --- Backward-compatible methods ---

  /// Store auth data (called after login/register for backward compat).
  static Future<void> storeAuthData(String token, Map<String, dynamic> userInfo) async {
    // Firebase handles token internally; just persist location if present
    final location = userInfo['location'] as String?;
    if (location != null && location.isNotEmpty) {
      await _parseAndStoreLocation(location);
    }
  }

  /// Load auth state — checks if Firebase user is signed in.
  static Future<bool> loadAuthData() async {
    await _loadLocation();
    return _auth.currentUser != null;
  }

  /// Clear auth data (logout alias).
  static Future<void> clearAuthData() async {
    await logout();
  }

  // --- Location ---

  /// Set the user's location explicitly.
  static Future<void> setLocation({String? state, String? district}) async {
    _userState = state;
    _userDistrict = district;
    final prefs = await SharedPreferences.getInstance();
    if (state != null) {
      await prefs.setString('user_state', state);
    } else {
      await prefs.remove('user_state');
    }
    if (district != null) {
      await prefs.setString('user_district', district);
    } else {
      await prefs.remove('user_district');
    }
  }

  static Future<void> _loadLocation() async {
    final prefs = await SharedPreferences.getInstance();
    _userState = prefs.getString('user_state');
    _userDistrict = prefs.getString('user_district');
  }

  /// Parse "Lucknow, UP" into state + district.
  static Future<void> _parseAndStoreLocation(String location) async {
    final prefs = await SharedPreferences.getInstance();
    const stateMap = {
      'UP': 'UP', 'UTTAR PRADESH': 'UP',
      'MP': 'MP', 'MADHYA PRADESH': 'MP',
      'MH': 'MH', 'MAHARASHTRA': 'MH',
      'PB': 'PB', 'PUNJAB': 'PB',
      'KA': 'KA', 'KARNATAKA': 'KA',
      'RJ': 'RJ', 'RAJASTHAN': 'RJ',
      'BR': 'BR', 'BIHAR': 'BR',
      'GJ': 'GJ', 'GUJARAT': 'GJ',
      'TN': 'TN', 'TAMIL NADU': 'TN',
      'WB': 'WB', 'WEST BENGAL': 'WB',
      'AP': 'AP', 'ANDHRA PRADESH': 'AP',
      'TS': 'TS', 'TELANGANA': 'TS',
      'HR': 'HR', 'HARYANA': 'HR',
    };

    final parts = location.split(',').map((s) => s.trim()).where((s) => s.isNotEmpty).toList();

    if (parts.length >= 2) {
      final stateRaw = parts.last.toUpperCase();
      final stateCode = stateMap[stateRaw] ?? stateRaw;
      _userState = stateCode;
      _userDistrict = parts.first;
      await prefs.setString('user_state', stateCode);
      await prefs.setString('user_district', parts.first);
    } else if (parts.length == 1) {
      final raw = parts.first.toUpperCase();
      final stateCode = stateMap[raw];
      if (stateCode != null) {
        _userState = stateCode;
        await prefs.setString('user_state', stateCode);
      } else {
        _userDistrict = parts.first;
        await prefs.setString('user_district', parts.first);
      }
    }
  }

  // --- Authenticated API call helper ---

  /// Send authenticated chat message via backend.
  static Future<Map<String, dynamic>?> sendChatMessage(String message) async {
    // For Firebase Auth, we use the ID token for backend calls
    final idToken = await getIdToken();
    if (idToken == null) return null;

    try {
      final payload = <String, dynamic>{'message': message};
      if (locationPayload != null) {
        payload['location'] = locationPayload;
      }

      final response = await _httpPost(
        '/chat/send',
        payload,
        idToken,
      );
      return response;
    } catch (e) {
      print('Chat error: $e');
      return null;
    }
  }

  static Future<Map<String, dynamic>?> _httpPost(
    String path,
    Map<String, dynamic> body,
    String token,
  ) async {
    // Import http at top level if needed; for now delegate to ApiService
    return null; // Chat messages go through ApiService/ChatScreen directly
  }

  // --- Error mapping ---
  static String _mapAuthError(String code) {
    switch (code) {
      case 'email-already-in-use':
        return 'This email is already registered. Try logging in.';
      case 'invalid-email':
        return 'Invalid email address.';
      case 'weak-password':
        return 'Password is too weak. Use at least 6 characters.';
      case 'user-not-found':
        return 'No account found with this email.';
      case 'wrong-password':
        return 'Incorrect password.';
      case 'user-disabled':
        return 'This account has been disabled.';
      case 'too-many-requests':
        return 'Too many attempts. Please try again later.';
      case 'invalid-credential':
        return 'Invalid email or password.';
      default:
        return 'Authentication error: $code';
    }
  }
}
