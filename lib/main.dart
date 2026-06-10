import 'dart:ui';
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'core/app_export.dart';
import 'routes/app_routes.dart';
import 'services/auth_service.dart';
import 'services/analytics_service.dart';
import 'presentation/chat_screen/chat_screen.dart';
import 'presentation/auth_screen/login_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize Firebase (catches errors gracefully if google-services.json missing)
  try {
    await Firebase.initializeApp();

    // Route Flutter errors to Crashlytics
    FlutterError.onError = FirebaseCrashlytics.instance.recordFlutterFatalError;

    // Catch async errors
    PlatformDispatcher.instance.onError = (error, stack) {
      FirebaseCrashlytics.instance.recordError(error, stack, fatal: true);
      return true;
    };

    print('✅ Firebase initialized');
  } catch (e) {
    print('⚠️ Firebase not configured yet: $e');
    print('   Run: flutterfire configure --project=YOUR_PROJECT_ID');
  }

  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return ScreenUtilInit(
      designSize: const Size(393, 852),
      minTextAdapt: true,
      splitScreenMode: true,
      builder: (context, child) {
        return MaterialApp(
          title: 'KisanMitra AI',
          debugShowCheckedModeBanner: false,
          theme: ThemeData(
            primarySwatch: Colors.green,
            visualDensity: VisualDensity.adaptivePlatformDensity,
          ),
          navigatorObservers: [
            AnalyticsService.observer,
          ],
          home: AuthChecker(),
          routes: AppRoutes.routes,
        );
      },
    );
  }
}

/// Splash screen that checks auth state and routes accordingly.
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
    // Load persisted location data
    await AuthService.loadAuthData();

    // Show splash briefly
    await Future.delayed(const Duration(seconds: 1));

    if (mounted) {
      if (AuthService.isLoggedIn) {
        AnalyticsService.logScreenView('chat_screen');
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(builder: (context) => ChatScreen()),
        );
      } else {
        AnalyticsService.logScreenView('login_screen');
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(builder: (context) => LoginScreen()),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.green[50],
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              '🌾 KisanMitra AI',
              style: TextStyle(
                fontSize: 36,
                fontWeight: FontWeight.bold,
                color: Colors.green[800],
              ),
            ),
            const SizedBox(height: 16),
            Text(
              'Agricultural Intelligence Platform',
              style: TextStyle(
                fontSize: 18,
                color: Colors.green[600],
              ),
            ),
            const SizedBox(height: 40),
            CircularProgressIndicator(
              color: Colors.green[700],
            ),
          ],
        ),
      ),
    );
  }
}
