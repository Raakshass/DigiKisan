import 'package:flutter/material.dart';

String _appTheme = "lightCode";
LightCodeColors get appTheme => ThemeHelper().themeColor();
ThemeData get theme => ThemeHelper().themeData();

/// Helper class for managing themes and colors.

// ignore_for_file: must_be_immutable
class ThemeHelper {
  // A map of custom color themes supported by the app
  Map<String, LightCodeColors> _supportedCustomColor = {
    'lightCode': LightCodeColors()
  };

  // A map of color schemes supported by the app
  Map<String, ColorScheme> _supportedColorScheme = {
    'lightCode': ColorSchemes.lightCodeColorScheme
  };

  /// Changes the app theme to [_newTheme].
  void changeTheme(String _newTheme) {
    _appTheme = _newTheme;
  }

  /// Returns the lightCode colors for the current theme.
  LightCodeColors _getThemeColors() {
    return _supportedCustomColor[_appTheme] ?? LightCodeColors();
  }

  /// Returns the current theme data.
  ThemeData _getThemeData() {
    var colorScheme =
        _supportedColorScheme[_appTheme] ?? ColorSchemes.lightCodeColorScheme;
    return ThemeData(
      visualDensity: VisualDensity.standard,
      colorScheme: colorScheme,
    );
  }

  /// Returns the lightCode colors for the current theme.
  LightCodeColors themeColor() => _getThemeColors();

  /// Returns the current theme data.
  ThemeData themeData() => _getThemeData();
}

class ColorSchemes {
  static final lightCodeColorScheme = ColorScheme.light();
}

class LightCodeColors {
  // App Colors
  Color get black => Color(0xFF1E1E1E);
  Color get white => Color(0xFFFFFFFF);
  Color get gray50 => Color(0xFFF9FAFB);
  Color get gray100 => Color(0xFFF3F4F6);
  Color get gray800 => Color(0xFF1F2937);
  Color get green500 => Color(0xFF10B981);
  Color get green700 => Color(0xFF047857);
  Color get green800 => Color(0xFF065F46);
  Color get gray500 => Color(0xFF6B7280);
  Color get gray400 => Color(0xFF9CA3AF);
  Color get gray10001 => Color(0xFFF5F5F5); // Add if missing
  Color get gray40001 => Color(0xFF9E9E9E); // Add if missing  

  // Additional Colors
  Color get whiteCustom => Colors.white;
  Color get blackCustom => Colors.black;
  Color get greyCustom => Colors.grey;
  Color get transparentCustom => Colors.transparent;
  Color get greenCustom => Colors.green;
  Color get colorFFF9FA => Color(0xFFF9FAFB);
  Color get colorFFF3F4 => Color(0xFFF3F4F6);
  Color get colorFF1F29 => Color(0xFF1F2937);
  Color get colorFF10B9 => Color(0xFF10B981);
  Color get colorFF0596 => Color(0xFF059669);
  Color get colorFF065F => Color(0xFF065F46);
  Color get colorFF6B72 => Color(0xFF6B7280);
  Color get colorFFF9F9 => Color(0xFFF9F9FA);
  Color get colorFFFFFC => Color(0xFFFFFCF8);
  Color get color888888 => Color(0x88888888);
  Color get colorFF1C1C => Color(0xFF1C1C1C);
  Color get colorFF353B => Color(0xFF353B41);

  // Color Shades - Each shade has its own dedicated constant
  Color get grey800 => Colors.grey.shade800;
  Color get grey200 => Colors.grey.shade200;
  Color get grey100 => Colors.grey.shade100;
}
