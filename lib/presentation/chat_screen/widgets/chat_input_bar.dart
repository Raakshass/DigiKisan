import 'package:flutter/material.dart';
import 'package:digikisan/core/app_export.dart';
import 'package:digikisan/widgets/custom_button.dart';

/// Chat input bar with text field, voice recording, image upload, and send button.
/// Extracted from chat_screen.dart for reusability and testability.
class ChatInputBar extends StatelessWidget {
  final TextEditingController textController;
  final bool isLoading;
  final bool isRecording;
  final bool isPlayingResponse;
  final bool inConversation;
  final bool isDiseaseConversationActive;
  final String selectedLanguageName;
  final VoidCallback onSend;
  final VoidCallback onImageUpload;
  final VoidCallback onVoiceToggle;
  final VoidCallback? onNewChat;

  const ChatInputBar({
    Key? key,
    required this.textController,
    required this.isLoading,
    required this.isRecording,
    required this.isPlayingResponse,
    required this.inConversation,
    required this.isDiseaseConversationActive,
    required this.selectedLanguageName,
    required this.onSend,
    required this.onImageUpload,
    required this.onVoiceToggle,
    this.onNewChat,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: appTheme.whiteCustom,
        borderRadius: BorderRadius.only(
          topLeft: Radius.circular(24.h),
          topRight: Radius.circular(24.h),
        ),
        boxShadow: [
          BoxShadow(
            color: appTheme.blackCustom.withAlpha(26),
            blurRadius: 10.h,
            offset: Offset(0, -2.h),
          ),
        ],
        border: Border(
          top: BorderSide(color: appTheme.colorFFF3F4, width: 1.h),
        ),
      ),
      padding: EdgeInsets.all(16.h),
      child: Column(
        children: [
          _buildTextField(),
          SizedBox(height: 16.h),
          _buildActionButtons(),
        ],
      ),
    );
  }

  Widget _buildTextField() {
    return TextField(
      controller: textController,
      decoration: InputDecoration(
        hintText: _getHintText(),
        hintStyle: TextStyleHelper.instance.body14.copyWith(
          color: isRecording ? appTheme.colorFF065F : appTheme.colorFF6B72,
        ),
        border: InputBorder.none,
        enabledBorder: InputBorder.none,
        focusedBorder: InputBorder.none,
        contentPadding: EdgeInsets.zero,
        suffixIcon: isLoading
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            : null,
      ),
      style: TextStyleHelper.instance.body14,
      onSubmitted: (_) => onSend(),
      maxLines: 3,
      minLines: 1,
    );
  }

  String _getHintText() {
    if (isRecording) return "🎤 Recording in $selectedLanguageName...";
    if (isLoading) return 'Thinking...';
    if (isDiseaseConversationActive) {
      return 'Ask about treatment, prevention, next steps...';
    }
    if (inConversation) return 'Ask anything about farming...';
    return 'Ask about crop prices, diseases, weather...';
  }

  Widget _buildActionButtons() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Row(
          children: [
            if (inConversation && onNewChat != null) ...[
              CustomButton(
                variant: CustomButtonVariant.filled,
                text: 'New Chat',
                backgroundColor: appTheme.colorFF6B72,
                textColor: appTheme.whiteCustom,
                borderRadius: 12.h,
                fontSize: 12.fSize,
                fontWeight: FontWeight.w400,
                padding: EdgeInsets.symmetric(
                  horizontal: 12.h,
                  vertical: 6.h,
                ),
                onPressed: onNewChat,
              ),
              SizedBox(width: 8.h),
            ],
            // Camera / image upload
            CustomButton(
              variant: CustomButtonVariant.icon,
              iconPath: ImageConstant.imgButtonBlueGray90001,
              width: 28.h,
              height: 28.h,
              borderColor: appTheme.blackCustom,
              borderRadius: 12.h,
              onPressed: onImageUpload,
            ),
            SizedBox(width: 8.h),
            // Microphone
            GestureDetector(
              onTap: onVoiceToggle,
              child: Container(
                width: 28.h,
                height: 28.h,
                decoration: BoxDecoration(
                  color: isRecording
                      ? appTheme.colorFF065F
                      : appTheme.whiteCustom,
                  borderRadius: BorderRadius.circular(12.h),
                  border: Border.all(
                    color: isRecording
                        ? appTheme.colorFF065F
                        : appTheme.blackCustom,
                    width: 1.h,
                  ),
                ),
                child: Icon(
                  isRecording ? Icons.stop : Icons.mic,
                  color: isRecording
                      ? appTheme.whiteCustom
                      : appTheme.colorFF065F,
                  size: 16.h,
                ),
              ),
            ),
            SizedBox(width: 8.h),
            // File attachment
            CustomButton(
              variant: CustomButtonVariant.icon,
              iconPath: ImageConstant.imgButtonBlueGray9000128x28,
              width: 28.h,
              height: 28.h,
              borderColor: appTheme.blackCustom,
              borderRadius: 12.h,
              onPressed: () => print('File attachment opened'),
            ),
          ],
        ),
        // Send button
        CustomButton(
          variant: CustomButtonVariant.filled,
          text: isLoading ? 'Thinking...' : 'Send',
          backgroundColor:
              isLoading ? appTheme.colorFF6B72 : appTheme.colorFF065F,
          textColor: appTheme.whiteCustom,
          borderRadius: 12.h,
          fontSize: 14.fSize,
          fontWeight: FontWeight.w500,
          padding: EdgeInsets.symmetric(horizontal: 20.h, vertical: 8.h),
          onPressed: isLoading ? null : onSend,
        ),
      ],
    );
  }
}
