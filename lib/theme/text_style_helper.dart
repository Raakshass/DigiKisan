import 'package:flutter/material.dart';
import '../core/app_export.dart';

/// A helper class for managing text styles in the application
class TextStyleHelper {
  static TextStyleHelper? _instance;

  TextStyleHelper._();

  static TextStyleHelper get instance {
    _instance ??= TextStyleHelper._();
    return _instance!;
  }

  // Title Styles
  // Medium text styles for titles and subtitles

  TextStyle get title20RegularRoboto => TextStyle(
        fontSize: 20.fSize,
        fontWeight: FontWeight.w400,
        fontFamily: 'Roboto',
      );

  TextStyle get title18Bold => TextStyle(
        fontSize: 18.fSize,
        fontWeight: FontWeight.bold,
        color: appTheme.colorFF1F29,
      );

  TextStyle get title16SemiBold => TextStyle(
        fontSize: 16.fSize,
        fontWeight: FontWeight.w600,
        color: appTheme.colorFF065F,
      );

  // Body Styles
  // Standard text styles for body content

  TextStyle get body14Bold => TextStyle(
        fontSize: 14.fSize,
        fontWeight: FontWeight.bold,
        color: appTheme.blackCustom,
      );

  TextStyle get body14 => TextStyle(
        fontSize: 14.fSize,
        color: appTheme.blackCustom,
      );

  TextStyle get body12 => TextStyle(
        fontSize: 12.fSize,
        color: appTheme.colorFF0596,
      );

  // ✅ NEW: Quick Action Chip Text Style (Inter Regular 12pt with proper line height)
  TextStyle get chipText => TextStyle(
        fontFamily: 'Inter',
        fontWeight: FontWeight.w400,
        fontSize: 12.fSize,
        height: 16 / 12, // 16px line height / 12px font size = 1.33
        color: appTheme.colorFF065F,
      );

  // Other Styles
  // Miscellaneous text styles without specified font size

  TextStyle get textStyle7 => TextStyle();
}
