import 'package:flutter/material.dart';

import '../../core/app_export.dart';
import '../../widgets/custom_button.dart';
import '../../widgets/custom_image_view.dart';

class MenuScreen extends StatelessWidget {
  MenuScreen({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: appTheme.colorFFF9FA,
      body: SafeArea(
        child: Column(
          children: [
            _buildHeaderSection(context),
            Expanded(
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _buildTodaySection(context),
                    _buildYesterdaySection(context),
                    _buildLast7DaysSection(context),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeaderSection(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: appTheme.whiteCustom,
        boxShadow: [
          BoxShadow(
            color: appTheme.blackCustom.withAlpha(26),
            blurRadius: 10.h,
            offset: Offset(0, 2.h),
          ),
        ],
      ),
      padding: EdgeInsets.symmetric(horizontal: 16.h, vertical: 24.h),
      child: Column(
        children: [
          // Back button row
          Row(
            children: [
              IconButton(
                onPressed: () => Navigator.pop(context),
                icon: Icon(Icons.arrow_back, color: appTheme.colorFF1F29, size: 24.h),
                padding: EdgeInsets.zero,
                constraints: BoxConstraints(),
              ),
              Spacer(),
            ],
          ),
          SizedBox(height: 8.h),
          // Logo
          CustomImageView(
            imagePath: ImageConstant.imgLogo,
            height: 84.h,
            width: 89.h,
          ),
          SizedBox(height: 24.h),
          // Search bar
          Row(
            children: [
              Expanded(
                child: Container(
                  height: 40.h,
                  decoration: BoxDecoration(
                    color: appTheme.whiteCustom,
                    border: Border.all(color: appTheme.colorFF1C1C),
                    borderRadius: BorderRadius.circular(8.h),
                  ),
                  child: TextField(
                    decoration: InputDecoration(
                      hintText: 'Search',
                      hintStyle: TextStyleHelper.instance.body14
                          .copyWith(color: appTheme.colorFF353B),
                      border: InputBorder.none,
                      contentPadding: EdgeInsets.symmetric(horizontal: 16.h),
                    ),
                    style: TextStyleHelper.instance.body14
                        .copyWith(color: appTheme.colorFF353B),
                  ),
                ),
              ),
              SizedBox(width: 8.h),
              Container(
                height: 40.h,
                width: 40.h,
                decoration: BoxDecoration(
                  color: appTheme.whiteCustom,
                  border: Border.all(color: appTheme.colorFF1C1C),
                  borderRadius: BorderRadius.circular(12.h),
                ),
                child: Center(
                  child: CustomImageView(
                    imagePath: ImageConstant.imgButton,
                    height: 20.h,
                    width: 20.h,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  // ✅ NEW: Chat History Card Builder
  Widget _buildChatHistoryCard({
    required String iconPath,
    required String message,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: EdgeInsets.only(bottom: 12.h),
        padding: EdgeInsets.all(16.h),
        decoration: BoxDecoration(
          color: appTheme.whiteCustom,
          borderRadius: BorderRadius.circular(12.h),
          border: Border.all(color: appTheme.colorFFF3F4, width: 1.h),
          boxShadow: [
            BoxShadow(
              color: appTheme.blackCustom.withAlpha(13),
              blurRadius: 4.h,
              offset: Offset(0, 1.h),
            ),
          ],
        ),
        child: Row(
          children: [
            // Icon container
            Container(
              width: 40.h,
              height: 40.h,
              decoration: BoxDecoration(
                color: appTheme.colorFFF9FA,
                borderRadius: BorderRadius.circular(20.h),
              ),
              child: Center(
                child: CustomImageView(
                  imagePath: iconPath,
                  height: 20.h,
                  width: 20.h,
                  color: appTheme.colorFF065F,
                ),
              ),
            ),
            SizedBox(width: 12.h),
            // Message text
            Expanded(
              child: Text(
                message,
                style: TextStyleHelper.instance.body14.copyWith(
                  height: 1.3,
                  color: appTheme.colorFF1F29,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ),
            // Arrow icon
            Icon(
              Icons.arrow_forward_ios,
              size: 16.h,
              color: appTheme.colorFF6B72,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTodaySection(BuildContext context) {
    return Container(
      padding: EdgeInsets.all(16.h),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Section header
          Text(
            'Today',
            style: TextStyleHelper.instance.body12.copyWith(
              color: appTheme.colorFF6B72,
              fontWeight: FontWeight.w600,
            ),
          ),
          SizedBox(height: 16.h),
          // Chat history cards
          _buildChatHistoryCard(
            iconPath: ImageConstant.imgPlant,
            message: 'How to treat yellow spots on wheat leaves?',
            onTap: () => Navigator.pop(context),
          ),
          _buildChatHistoryCard(
            iconPath: ImageConstant.imgPrices,
            message: 'Potato price today in Agra',
            onTap: () => Navigator.pop(context),
          ),
          _buildChatHistoryCard(
            iconPath: ImageConstant.imgFiles,
            message: 'Government scheme for irrigation support',
            onTap: () => Navigator.pop(context),
          ),
          _buildChatHistoryCard(
            iconPath: ImageConstant.imgMenuWeather,
            message: 'Rain forecast for the next 3 days',
            onTap: () => Navigator.pop(context),
          ),
        ],
      ),
    );
  }

  Widget _buildYesterdaySection(BuildContext context) {
    return Container(
      padding: EdgeInsets.all(16.h),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Yesterday',
            style: TextStyleHelper.instance.body12.copyWith(
              color: appTheme.colorFF6B72,
              fontWeight: FontWeight.w600,
            ),
          ),
          SizedBox(height: 16.h),
          _buildChatHistoryCard(
            iconPath: ImageConstant.imgPlant,
            message: 'Best fertilizer for rice in July',
            onTap: () => Navigator.pop(context),
          ),
          _buildChatHistoryCard(
            iconPath: ImageConstant.imgMenuCamera,
            message: 'Upload photo – pest on tomato plant',
            onTap: () => Navigator.pop(context),
          ),
          _buildChatHistoryCard(
            iconPath: ImageConstant.imgQuestion,
            message: 'What is PM-KISAN and how to apply?',
            onTap: () => Navigator.pop(context),
          ),
        ],
      ),
    );
  }

  Widget _buildLast7DaysSection(BuildContext context) {
    return Container(
      padding: EdgeInsets.all(16.h),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Last 7 days',
            style: TextStyleHelper.instance.body12.copyWith(
              color: appTheme.colorFF6B72,
              fontWeight: FontWeight.w600,
            ),
          ),
          SizedBox(height: 16.h),
          _buildChatHistoryCard(
            iconPath: ImageConstant.imgFiles,
            message: 'Subsidy available for tractors in 2025',
            onTap: () => Navigator.pop(context),
          ),
          _buildChatHistoryCard(
            iconPath: ImageConstant.imgQuestion,
            message: 'When to harvest sugarcane this season?',
            onTap: () => Navigator.pop(context),
          ),
          _buildChatHistoryCard(
            iconPath: ImageConstant.imgMenuWeather,
            message: 'How to improve soil health after monsoon',
            onTap: () => Navigator.pop(context),
          ),
        ],
      ),
    );
  }
}
