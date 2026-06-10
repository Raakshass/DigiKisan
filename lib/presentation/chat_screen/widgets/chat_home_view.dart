import 'package:flutter/material.dart';
import 'package:digikisan/core/app_export.dart';
import 'package:digikisan/widgets/custom_image_view.dart';

/// Home view shown when not in active conversation.
/// Contains user welcome, info cards, greeting, and quick action chips.
class ChatHomeView extends StatelessWidget {
  final String? userName;
  final String? userEmail;
  final VoidCallback onDiagnoseCrop;
  final VoidCallback onCheckPrices;
  final VoidCallback onGovSchemes;
  final VoidCallback onWeatherSoil;

  const ChatHomeView({
    Key? key,
    this.userName,
    this.userEmail,
    required this.onDiagnoseCrop,
    required this.onCheckPrices,
    required this.onGovSchemes,
    required this.onWeatherSoil,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        if (userName != null) _buildUserWelcome(),
        _buildInfoCards(),
        _buildGreeting(),
        _buildQuickActionChips(context),
      ],
    );
  }

  Widget _buildUserWelcome() {
    return Container(
      margin: EdgeInsets.all(16.h),
      padding: EdgeInsets.all(16.h),
      decoration: BoxDecoration(
        color: appTheme.colorFF065F.withAlpha(20),
        borderRadius: BorderRadius.circular(12.h),
      ),
      child: Row(
        children: [
          CircleAvatar(
            radius: 20.h,
            backgroundColor: appTheme.colorFF065F,
            child: Text(
              userName!.substring(0, 1).toUpperCase(),
              style: TextStyle(
                color: appTheme.whiteCustom,
                fontSize: 16.fSize,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          SizedBox(width: 12.h),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Welcome back, $userName!',
                  style: TextStyleHelper.instance.body14Bold,
                ),
                if (userEmail != null && userEmail!.isNotEmpty)
                  Text(
                    userEmail!,
                    style: TextStyleHelper.instance.body12.copyWith(
                      color: appTheme.colorFF6B72,
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInfoCards() {
    return Padding(
      padding: EdgeInsets.symmetric(horizontal: 16.h, vertical: 24.h),
      child: Row(
        children: [
          Expanded(child: _buildWeatherCard()),
          SizedBox(width: 16.h),
          Expanded(child: _buildPriceCard()),
        ],
      ),
    );
  }

  Widget _buildWeatherCard() {
    return Container(
      decoration: BoxDecoration(
        color: appTheme.whiteCustom,
        borderRadius: BorderRadius.circular(12.h),
        border: Border.all(color: appTheme.colorFF10B9, width: 1.h),
        boxShadow: [
          BoxShadow(
            color: appTheme.blackCustom.withAlpha(26),
            blurRadius: 10.h,
            offset: Offset(0, 2.h),
          ),
        ],
      ),
      padding: EdgeInsets.all(16.h),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('📍Nagpur', style: TextStyleHelper.instance.body12),
              CustomImageView(
                imagePath: ImageConstant.imgSun,
                height: 24.h,
                width: 24.h,
              ),
            ],
          ),
          SizedBox(height: 12.h),
          Row(
            children: [
              Text('30°C', style: TextStyleHelper.instance.body14Bold),
              SizedBox(width: 8.h),
              Text('Sunny', style: TextStyleHelper.instance.body12),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildPriceCard() {
    return Container(
      decoration: BoxDecoration(
        color: appTheme.whiteCustom,
        borderRadius: BorderRadius.circular(12.h),
        border: Border.all(color: appTheme.colorFF10B9, width: 1.h),
        boxShadow: [
          BoxShadow(
            color: appTheme.blackCustom.withAlpha(26),
            blurRadius: 10.h,
            offset: Offset(0, 2.h),
          ),
        ],
      ),
      padding: EdgeInsets.all(16.h),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('🥔 Potato', style: TextStyleHelper.instance.body12),
              CustomImageView(
                imagePath: ImageConstant.imgCurrencycircledollar,
                height: 24.h,
                width: 24.h,
              ),
            ],
          ),
          SizedBox(height: 12.h),
          Row(
            children: [
              Text('₹2250', style: TextStyleHelper.instance.body14Bold),
              SizedBox(width: 8.h),
              Text('/quintal', style: TextStyleHelper.instance.body12),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildGreeting() {
    return Padding(
      padding: EdgeInsets.symmetric(horizontal: 16.h, vertical: 32.h),
      child: Text(
        userName != null
            ? 'Hello $userName!\nHow can I help your farm today?'
            : 'Hello!\nHow can I help your farm today?',
        textAlign: TextAlign.center,
        style: TextStyleHelper.instance.title16SemiBold
            .copyWith(height: 1.5),
      ),
    );
  }

  Widget _buildQuickActionChips(BuildContext context) {
    return Padding(
      padding: EdgeInsets.symmetric(horizontal: 16.h),
      child: GridView.count(
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        crossAxisCount: 2,
        crossAxisSpacing: 12.h,
        mainAxisSpacing: 12.h,
        childAspectRatio: 2.5,
        children: [
          _buildChip(
            iconPath: ImageConstant.imgMenuCamera,
            text: 'Diagnose Crop Disease',
            onTap: onDiagnoseCrop,
          ),
          _buildChip(
            iconPath: ImageConstant.imgPrices,
            text: 'Check Crop Prices',
            onTap: onCheckPrices,
          ),
          _buildChip(
            iconPath: ImageConstant.imgMenuCamera,
            text: 'Government Schemes',
            onTap: onGovSchemes,
          ),
          _buildChip(
            iconPath: ImageConstant.imgMenuWeather,
            text: 'Weather and Soil',
            onTap: onWeatherSoil,
          ),
        ],
      ),
    );
  }

  Widget _buildChip({
    required String iconPath,
    required String text,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        decoration: BoxDecoration(
          color: appTheme.whiteCustom,
          borderRadius: BorderRadius.circular(16.h),
          border: Border.all(
            color: appTheme.blackCustom.withValues(alpha: 0.1),
            width: 1.h,
          ),
          boxShadow: [
            BoxShadow(
              color: appTheme.blackCustom.withAlpha(13),
              blurRadius: 4.h,
              offset: Offset(0, 1.h),
            ),
          ],
        ),
        padding: EdgeInsets.symmetric(horizontal: 12.h, vertical: 8.h),
        child: Row(
          children: [
            CustomImageView(
              imagePath: iconPath,
              height: 16.h,
              width: 16.h,
              color: appTheme.colorFF065F,
            ),
            SizedBox(width: 8.h),
            Expanded(
              child: Text(
                text,
                style: TextStyleHelper.instance.chipText,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
