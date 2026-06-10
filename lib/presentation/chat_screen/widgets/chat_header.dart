import 'package:flutter/material.dart';
import 'package:digikisan/core/app_export.dart';
import 'package:digikisan/widgets/custom_button.dart';
import 'package:digikisan/widgets/custom_image_view.dart';
import 'package:digikisan/widgets/language_selector.dart';
import 'package:digikisan/presentation/menu_screen/menu_screen.dart';

/// Slide transition for menu navigation.
class SlideLeftRoute extends PageRouteBuilder {
  final Widget page;
  SlideLeftRoute({required this.page})
      : super(
          pageBuilder: (_, __, ___) => page,
          transitionsBuilder: (_, animation, __, child) => SlideTransition(
            position:
                Tween<Offset>(begin: const Offset(-1, 0), end: Offset.zero)
                    .animate(CurvedAnimation(
                        parent: animation, curve: Curves.easeInOut)),
            child: child,
          ),
          transitionDuration: const Duration(milliseconds: 300),
        );
}

/// Chat header bar with menu, title, location indicator, language selector, and overflow menu.
class ChatHeader extends StatelessWidget {
  final String selectedLanguage;
  final String selectedLanguageName;
  final ValueChanged<MapEntry<String, String>> onLanguageChanged;
  final VoidCallback onLogout;
  final String? userState;
  final String? userDistrict;

  const ChatHeader({
    Key? key,
    required this.selectedLanguage,
    required this.selectedLanguageName,
    required this.onLanguageChanged,
    required this.onLogout,
    this.userState,
    this.userDistrict,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
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
        border: Border(
          bottom: BorderSide(color: appTheme.colorFFF3F4, width: 1.h),
        ),
      ),
      padding: EdgeInsets.symmetric(horizontal: 16.h, vertical: 16.h),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          // Menu button
          CustomButton(
            variant: CustomButtonVariant.icon,
            iconPath: ImageConstant.imgButtonBlueGray900,
            width: 40.h,
            height: 40.h,
            borderColor: appTheme.colorFF1F29,
            borderRadius: 12.h,
            onPressed: () {
              Navigator.of(context)
                  .push(SlideLeftRoute(page: MenuScreen()));
            },
          ),
          // Title + location
          Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  CustomImageView(
                    imagePath: ImageConstant.imgSproutGraphic1,
                    height: 16.h,
                    width: 16.h,
                  ),
                  SizedBox(width: 8.h),
                  Text('KisanMitra AI', style: TextStyleHelper.instance.title18Bold),
                ],
              ),
              // Location indicator
              if (userState != null || userDistrict != null)
                Padding(
                  padding: EdgeInsets.only(top: 2.h),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        Icons.location_on,
                        size: 12.h,
                        color: appTheme.colorFF065F,
                      ),
                      SizedBox(width: 2.h),
                      Text(
                        [
                          if (userDistrict != null) userDistrict!,
                          if (userState != null) userState!,
                        ].join(', '),
                        style: TextStyle(
                          fontSize: 11.h,
                          color: appTheme.colorFF065F,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
          // Actions
          Row(
            children: [
              LanguageSelector(
                selectedLanguage: selectedLanguage,
                selectedLanguageName: selectedLanguageName,
                onLanguageChanged: (code, name) {
                  onLanguageChanged(MapEntry(code, name));
                },
              ),
              SizedBox(width: 8.h),
              PopupMenuButton<String>(
                icon: Icon(Icons.more_vert, color: appTheme.colorFF065F),
                onSelected: (value) {
                  if (value == 'logout') onLogout();
                },
                itemBuilder: (context) => [
                  PopupMenuItem(
                    value: 'logout',
                    child: Row(
                      children: [
                        Icon(Icons.logout, color: appTheme.colorFF065F),
                        SizedBox(width: 8.h),
                        Text('Logout'),
                      ],
                    ),
                  ),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }
}
