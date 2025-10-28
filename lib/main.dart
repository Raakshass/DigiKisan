import 'package:flutter/material.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';
import 'core/app_export.dart';
import 'routes/app_routes.dart';
import 'services/auth_service.dart';
import 'presentation/chat_screen/chat_screen.dart';
import 'presentation/auth_screen/login_screen.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return ScreenUtilInit(
      designSize: const Size(393, 852), // ✅ Your Figma design size
      minTextAdapt: true,              // ✅ Adapt text size automatically
      splitScreenMode: true,           // ✅ Fix for splitScreenMode error
      builder: (context, child) {
        return MaterialApp(
          title: 'DigiKisan',
          debugShowCheckedModeBanner: false,
          theme: ThemeData(
            primarySwatch: Colors.green,
            visualDensity: VisualDensity.adaptivePlatformDensity,
          ),
          home: AuthChecker(), // ✅ Check authentication first
          routes: AppRoutes.routes,
        );
      },
    );
  }
}

// Widget to check if user is already logged in
class AuthChecker extends StatefulWidget {
  @override
  _AuthCheckerState createState() => _AuthCheckerState();
}

class _AuthCheckerState extends State<AuthChecker> {
  @override
  void initState() {
    super.initState();
    _checkAuth();
  }

  Future<void> _checkAuth() async {
    // Check if user is already logged in
    bool isLoggedIn = await AuthService.loadAuthData();
    
    // Wait a moment to show splash
    await Future.delayed(Duration(seconds: 1));
    
    if (mounted) {
      if (isLoggedIn) {
        // User is logged in, go to chat
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(builder: (context) => ChatScreen()),
        );
      } else {
        // User not logged in, go to login
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(builder: (context) => LoginScreen()),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    // Show splash screen while checking
    return Scaffold(
      backgroundColor: Colors.green[50],
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              '🌾 DigiKisan',
              style: TextStyle(
                fontSize: 36, // ✅ Fixed: Removed .sp
                fontWeight: FontWeight.bold,
                color: Colors.green[800],
              ),
            ),
            SizedBox(height: 16), // ✅ Fixed: Removed .h
            Text(
              'Agricultural Intelligence Platform',
              style: TextStyle(
                fontSize: 18, // ✅ Fixed: Removed .sp
                color: Colors.green[600],
              ),
            ),
            SizedBox(height: 40), // ✅ Fixed: Removed .h
            CircularProgressIndicator(
              color: Colors.green[700],
            ),
          ],
        ),
      ),
    );
  }
}
