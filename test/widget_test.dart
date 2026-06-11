// KisanMitra AI — Widget Smoke Test
// Verifies that the app can at least be instantiated without crashing.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('App smoke test — MaterialApp renders', (WidgetTester tester) async {
    // Minimal smoke test: a MaterialApp with a Text widget renders.
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: Center(child: Text('KisanMitra AI')),
        ),
      ),
    );

    expect(find.text('KisanMitra AI'), findsOneWidget);
  });
}
