import 'package:flutter/material.dart';

import '../core/app_export.dart';
import './custom_image_view.dart';

/// Custom button component that supports multiple variants including icon buttons,
/// outlined buttons, and filled buttons with configurable styling options.
///
/// Arguments:
/// - [text]: Button text content
/// - [onPressed]: Callback function when button is pressed
/// - [variant]: Button style variant (icon, outlined, filled)
/// - [iconPath]: Path to icon image for icon buttons
/// - [backgroundColor]: Background color of the button
/// - [borderColor]: Border color for outlined buttons
/// - [textColor]: Text color
/// - [width]: Button width (null for intrinsic width)
/// - [height]: Button height
/// - [padding]: Internal padding
/// - [borderRadius]: Border radius for rounded corners
/// - [fontSize]: Text font size
/// - [fontWeight]: Text font weight
/// - [isFullWidth]: Whether button should take full available width
class CustomButton extends StatelessWidget {
  const CustomButton({
    Key? key,
    this.text,
    this.onPressed,
    this.variant,
    this.iconPath,
    this.backgroundColor,
    this.borderColor,
    this.textColor,
    this.width,
    this.height,
    this.padding,
    this.borderRadius,
    this.fontSize,
    this.fontWeight,
    this.isFullWidth,
  }) : super(key: key);

  /// Text content of the button
  final String? text;

  /// Callback function triggered when button is pressed
  final VoidCallback? onPressed;

  /// Button style variant
  final CustomButtonVariant? variant;

  /// Path to icon image (for icon buttons)
  final String? iconPath;

  /// Background color of the button
  final Color? backgroundColor;

  /// Border color (for outlined buttons)
  final Color? borderColor;

  /// Text color
  final Color? textColor;

  /// Button width
  final double? width;

  /// Button height
  final double? height;

  /// Internal padding
  final EdgeInsetsGeometry? padding;

  /// Border radius
  final double? borderRadius;

  /// Text font size
  final double? fontSize;

  /// Text font weight
  final FontWeight? fontWeight;

  /// Whether button should take full available width
  final bool? isFullWidth;

  @override
  Widget build(BuildContext context) {
    final effectiveVariant = variant ?? CustomButtonVariant.filled;
    final effectiveHeight = height ?? 40.h;
    final effectiveBorderRadius = borderRadius ?? 12.h;
    final effectivePadding =
        padding ?? EdgeInsets.symmetric(horizontal: 16.h, vertical: 8.h);
    final effectiveFontSize = fontSize ?? 14.fSize;
    final effectiveFontWeight = fontWeight ?? FontWeight.w400;
    final shouldBeFullWidth = isFullWidth ?? false;

    Widget button = _buildButtonByVariant(
      effectiveVariant,
      effectiveHeight,
      effectiveBorderRadius,
      effectivePadding,
      effectiveFontSize,
      effectiveFontWeight,
    );

    if (shouldBeFullWidth) {
      return SizedBox(
        width: double.infinity,
        child: button,
      );
    }

    return width != null ? SizedBox(width: width, child: button) : button;
  }

  Widget _buildButtonByVariant(
    CustomButtonVariant variant,
    double height,
    double borderRadius,
    EdgeInsetsGeometry padding,
    double fontSize,
    FontWeight fontWeight,
  ) {
    switch (variant) {
      case CustomButtonVariant.icon:
        return _buildIconButton(height, borderRadius);
      case CustomButtonVariant.outlined:
        return _buildOutlinedButton(
            height, borderRadius, padding, fontSize, fontWeight);
      case CustomButtonVariant.filled:
        return _buildFilledButton(
            height, borderRadius, padding, fontSize, fontWeight);
    }
  }

  Widget _buildIconButton(double height, double borderRadius) {
    final effectiveBorderColor = borderColor ?? appTheme.grey800;

    return SizedBox(
      height: height,
      width: height,
      child: OutlinedButton(
        onPressed: onPressed,
        style: OutlinedButton.styleFrom(
          padding: EdgeInsets.all(8.h),
          side: BorderSide(color: effectiveBorderColor),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(borderRadius),
          ),
          backgroundColor: backgroundColor ?? appTheme.transparentCustom,
        ),
        child: iconPath != null
            ? CustomImageView(
                imagePath: iconPath!,
                height: 24.h,
                width: 24.h,
              )
            : Icon(
                Icons.menu,
                size: 24.h,
                color: appTheme.grey800,
              ),
      ),
    );
  }

  Widget _buildOutlinedButton(
    double height,
    double borderRadius,
    EdgeInsetsGeometry padding,
    double fontSize,
    FontWeight fontWeight,
  ) {
    final effectiveBackgroundColor = backgroundColor ?? appTheme.whiteCustom;
    final effectiveBorderColor = borderColor ?? appTheme.blackCustom;
    final effectiveTextColor = textColor ?? appTheme.green800;

    return OutlinedButton(
      onPressed: onPressed,
      style: OutlinedButton.styleFrom(
        minimumSize: Size(0, height),
        padding: padding,
        side: BorderSide(color: effectiveBorderColor),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(borderRadius),
        ),
        backgroundColor: effectiveBackgroundColor,
      ),
      child: Text(
        text ?? '',
        style: TextStyleHelper.instance.textStyle7,
      ),
    );
  }

  Widget _buildFilledButton(
    double height,
    double borderRadius,
    EdgeInsetsGeometry padding,
    double fontSize,
    FontWeight fontWeight,
  ) {
    final effectiveBackgroundColor = backgroundColor ?? Color(0xFFF9F9FA);
    final effectiveTextColor = textColor ?? appTheme.blackCustom;

    return ElevatedButton(
      onPressed: onPressed,
      style: ElevatedButton.styleFrom(
        minimumSize: Size(0, height),
        padding: padding,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(borderRadius),
        ),
        backgroundColor: effectiveBackgroundColor,
      ),
      child: Text(
        text ?? '',
        textAlign: TextAlign.left,
        style: TextStyleHelper.instance.textStyle7,
      ),
    );
  }
}

/// Button variant enum for different button styles
enum CustomButtonVariant {
  /// Icon button with border
  icon,

  /// Outlined button with text
  outlined,

  /// Filled button with background
  filled,
}
