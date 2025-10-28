import 'package:flutter/material.dart';
import 'package:flutter_screenutil/flutter_screenutil.dart';

// These are the Viewport values of your Figma Design.
// These are used in the code as a reference to create your UI Responsively.
const num FIGMA_DESIGN_WIDTH = 393;
const num FIGMA_DESIGN_HEIGHT = 852;
const num FIGMA_DESIGN_STATUS_BAR = 0;

// ✅ UPDATED: Enhanced responsive extension with .w, .h, .fSize
extension ResponsiveExtension on num {
  double get _width => SizeUtils.width;

  /// Get responsive width
  double get w => ScreenUtil().setWidth(this);

  /// Get responsive height  
  double get h => ScreenUtil().setHeight(this);

  /// Get responsive font size
  double get fSize => ScreenUtil().setSp(this);
  
  /// Alternative font size method
  double get sp => ScreenUtil().setSp(this);
}

extension FormatExtension on double {
  double toDoubleValue({int fractionDigits = 2}) {
    return double.parse(this.toStringAsFixed(fractionDigits));
  }

  double isNonZero({num defaultValue = 0.0}) {
    return this > 0 ? this : defaultValue.toDouble();
  }
}

enum DeviceType { mobile, tablet, desktop }

typedef ResponsiveBuild = Widget Function(
    BuildContext context, Orientation orientation, DeviceType deviceType);

class Sizer extends StatelessWidget {
  const Sizer({Key? key, required this.builder}) : super(key: key);

  /// Builds the widget whenever the orientation changes.
  final ResponsiveBuild builder;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (context, constraints) {
      return OrientationBuilder(builder: (context, orientation) {
        SizeUtils.setScreenSize(constraints, orientation);
        return builder(context, orientation, SizeUtils.deviceType);
      });
    });
  }
}

// ignore_for_file: must_be_immutable
class SizeUtils {
  /// Device's BoxConstraints
  static late BoxConstraints boxConstraints;

  /// Device's Orientation
  static late Orientation orientation;

  /// Type of Device
  /// This can either be mobile or tablet
  static late DeviceType deviceType;

  /// Device's Height
  static late double height;

  /// Device's Width
  static late double width;

  /// ✅ ADDED: Initialize with context for MediaQuery
  static void init(BuildContext context) {
    final mediaQueryData = MediaQuery.of(context);
    width = mediaQueryData.size.width;
    height = mediaQueryData.size.height;
  }

  static void setScreenSize(
    BoxConstraints constraints,
    Orientation currentOrientation,
  ) {
    boxConstraints = constraints;
    orientation = currentOrientation;
    if (orientation == Orientation.portrait) {
      width =
          boxConstraints.maxWidth.isNonZero(defaultValue: FIGMA_DESIGN_WIDTH);
      height = boxConstraints.maxHeight.isNonZero();
    } else {
      width =
          boxConstraints.maxHeight.isNonZero(defaultValue: FIGMA_DESIGN_WIDTH);
      height = boxConstraints.maxWidth.isNonZero();
    }
    
    // ✅ UPDATED: Enhanced device type detection
    deviceType = _getDeviceType();
  }

  /// ✅ ADDED: Smart device type detection
  static DeviceType _getDeviceType() {
    double deviceWidth = width;
    if (deviceWidth > 900) {
      return DeviceType.desktop;
    } else if (deviceWidth > 600) {
      return DeviceType.tablet;
    }
    return DeviceType.mobile;
  }
}

// ✅ ADDED: Additional utility extensions
extension ContextExtensions on BuildContext {
  /// Get screen width
  double get screenWidth => MediaQuery.of(this).size.width;
  
  /// Get screen height
  double get screenHeight => MediaQuery.of(this).size.height;
  
  /// Get device type
  DeviceType get deviceType => SizeUtils.deviceType;
  
  /// Check if device is mobile
  bool get isMobile => deviceType == DeviceType.mobile;
  
  /// Check if device is tablet
  bool get isTablet => deviceType == DeviceType.tablet;
  
  /// Check if device is desktop
  bool get isDesktop => deviceType == DeviceType.desktop;
}

// ✅ ADDED: Responsive breakpoints
class ResponsiveBreakpoints {
  static const double mobile = 600;
  static const double tablet = 900;
  static const double desktop = 1200;
}

// ✅ ADDED: Responsive helper functions
class ResponsiveHelper {
  static bool isMobile(BuildContext context) =>
      MediaQuery.of(context).size.width < ResponsiveBreakpoints.mobile;
      
  static bool isTablet(BuildContext context) =>
      MediaQuery.of(context).size.width >= ResponsiveBreakpoints.mobile &&
      MediaQuery.of(context).size.width < ResponsiveBreakpoints.tablet;
      
  static bool isDesktop(BuildContext context) =>
      MediaQuery.of(context).size.width >= ResponsiveBreakpoints.desktop;
      
  static T responsive<T>(
    BuildContext context, {
    required T mobile,
    T? tablet,
    T? desktop,
  }) {
    if (isDesktop(context) && desktop != null) return desktop;
    if (isTablet(context) && tablet != null) return tablet;
    return mobile;
  }
}
