import 'package:flutter/material.dart';
import '../presentation/auth_screen/login_screen.dart';
import '../presentation/chat_screen/chat_screen.dart';
import '../presentation/menu_screen/menu_screen.dart';

class AppRoutes {
  static const String loginScreen = '/login_screen';
  static const String chatScreen = '/chat_screen';
  static const String menuScreen = '/menu_screen';
  
  // ✅ CHANGED: Start with login screen
  static const String initialRoute = '/login_screen';

  static Map<String, WidgetBuilder> get routes => {
        loginScreen: (context) => LoginScreen(),
        chatScreen: (context) => ChatScreen(),
        menuScreen: (context) => MenuScreen(),
        // ✅ CHANGED: Initial route now goes to LoginScreen
        initialRoute: (context) => LoginScreen(),
      };
}
