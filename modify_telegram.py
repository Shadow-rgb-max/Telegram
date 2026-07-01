#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Android Client Modification Script
Adds "Add to Folder" dialog when subscribing to channels
"""

import sys
import os
import shutil
from datetime import datetime


def main(project_dir="."):
    print("=== Telegram Channel Subscribe Modification Script ===")
    print(f"Project directory: {project_dir}")

    chat_activity = os.path.join(
        project_dir,
        "TMessagesProj/src/main/java/org/telegram/ui/ChatActivity.java"
    )
    strings_xml = os.path.join(
        project_dir,
        "TMessagesProj/src/main/res/values/strings.xml"
    )

    # Check files
    if not os.path.isfile(chat_activity):
        print(f"ERROR: ChatActivity.java not found at {chat_activity}")
        sys.exit(1)

    if not os.path.isfile(strings_xml):
        print(f"ERROR: strings.xml not found at {strings_xml}")
        sys.exit(1)

    print("[1/4] Files found, starting modifications...")

    # ============================================================
    # STEP 1: Add string resources
    # ============================================================
    print("[2/4] Adding string resources...")

    with open(strings_xml, "r", encoding="utf-8") as f:
        strings_content = f.read()

    if 'name="AddToFolder"' not in strings_content:
        new_strings = """    <string name="AddToFolder">Add to Folder</string>
    <string name="DoNotAddToFolder">Don\'t Add to Folder</string>
</resources>"""
        strings_content = strings_content.replace("</resources>", new_strings)

        with open(strings_xml, "w", encoding="utf-8") as f:
            f.write(strings_content)
        print("       Added string resources")
    else:
        print("       String resources already exist, skipping")

    # ============================================================
    # STEP 2: Create backup of ChatActivity.java
    # ============================================================
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{chat_activity}.backup.{timestamp}"
    shutil.copy2(chat_activity, backup_file)
    print(f"[3/4] Backup created: {backup_file}")

    # ============================================================
    # STEP 3: Modify ChatActivity.java
    # ============================================================
    print("[4/4] Modifying ChatActivity.java...")

    with open(chat_activity, "r", encoding="utf-8") as f:
        content = f.read()

    # Check if already modified
    if "showFolderSelectionDialog" in content:
        print("Already modified, skipping...")
    else:
        # === PART 1: Replace the subscription block ===
        old_block = """                        } else {
                            if (chatInviteRunnable != null) {
                                AndroidUtilities.cancelRunOnUIThread(chatInviteRunnable);
                                chatInviteRunnable = null;
                            }
                            showBottomOverlayProgress(true, true);
                            getMessagesController().addUserToChat(currentChat.id, getUserConfig().getCurrentUser(), 0, null, ChatActivity.this, null);
                            NotificationCenter.getGlobalInstance().postNotificationName(NotificationCenter.closeSearchByActiveAction);

                            if (hasReportSpam() && reportSpamButton.getTag(R.id.object_tag) != null) {
                                SharedPreferences preferences = MessagesController.getNotificationsSettings(currentAccount);
                                preferences.edit().putInt("dialog_bar_vis3" + dialog_id, 3).commit();
                                getNotificationCenter().postNotificationName(NotificationCenter.peerSettingsDidLoad, dialog_id);
                            }
                        }"""

        new_block = """                        } else {
                            if (chatInviteRunnable != null) {
                                AndroidUtilities.cancelRunOnUIThread(chatInviteRunnable);
                                chatInviteRunnable = null;
                            }
                            showFolderSelectionDialog(() -> {
                                showBottomOverlayProgress(true, true);
                                getMessagesController().addUserToChat(currentChat.id, getUserConfig().getCurrentUser(), 0, null, ChatActivity.this, null);
                                NotificationCenter.getGlobalInstance().postNotificationName(NotificationCenter.closeSearchByActiveAction);

                                if (hasReportSpam() && reportSpamButton.getTag(R.id.object_tag) != null) {
                                    SharedPreferences preferences = MessagesController.getNotificationsSettings(currentAccount);
                                    preferences.edit().putInt("dialog_bar_vis3" + dialog_id, 3).commit();
                                    getNotificationCenter().postNotificationName(NotificationCenter.peerSettingsDidLoad, dialog_id);
                                }
                            });
                        }"""

        if old_block not in content:
            print("ERROR: Could not find the subscription block to replace")
            print("Searching for addUserToChat...")
            target = "getMessagesController().addUserToChat(currentChat.id, getUserConfig().getCurrentUser(), 0, null, ChatActivity.this, null)"
            if target in content:
                print("Found addUserToChat call but block boundaries do not match")
                print("Please check the exact indentation in your file")
            # Restore backup
            shutil.copy2(backup_file, chat_activity)
            sys.exit(1)

        content = content.replace(old_block, new_block)
        print("Replaced subscription block")

        # === PART 2: Add new methods at the end of the class ===
        new_methods = """
    // ===== MODIFICATION: Folder selection on channel subscribe =====

    /**
     * Shows BottomSheet with folder selection when subscribing to a channel.
     * After selection (or cancel), calls onComplete.
     */
    private void showFolderSelectionDialog(Runnable onComplete) {
        MessagesController messagesController = getMessagesController();
        ArrayList<MessagesController.DialogFilter> folders = messagesController.dialogFilters;

        if (folders == null || folders.isEmpty() || currentChat == null) {
            onComplete.run();
            return;
        }

        Context context = getContext();
        if (context == null) {
            onComplete.run();
            return;
        }

        final ArrayList<MessagesController.DialogFilter> availableFolders = new ArrayList<>();
        for (MessagesController.DialogFilter filter : folders) {
            if (filter != null && filter.id != 0) {
                availableFolders.add(filter);
            }
        }

        if (availableFolders.isEmpty()) {
            onComplete.run();
            return;
        }

        BottomSheet.Builder builder = new BottomSheet.Builder(context, themeDelegate);
        builder.setTitle(LocaleController.getString(R.string.AddToFolder));

        CharSequence[] items = new CharSequence[availableFolders.size() + 1];
        items[0] = LocaleController.getString(R.string.DoNotAddToFolder);
        for (int i = 0; i < availableFolders.size(); i++) {
            items[i + 1] = availableFolders.get(i).name;
        }

        builder.setItems(items, (dialog, which) -> {
            if (which > 0) {
                MessagesController.DialogFilter selectedFolder = availableFolders.get(which - 1);
                addDialogToFolder(dialog_id, selectedFolder.id);
            }
            onComplete.run();
        });

        BottomSheet sheet = builder.create();
        sheet.setOnDismissListener(dialog -> onComplete.run());
        showDialog(sheet);
    }

    /**
     * Adds dialog to specified folder (DialogFilter).
     */
    private void addDialogToFolder(long dialogId, int folderId) {
        MessagesController messagesController = getMessagesController();
        MessagesController.DialogFilter filter = messagesController.dialogFiltersById.get(folderId);
        if (filter == null) return;

        if (filter.alwaysShow.contains(dialogId)) {
            return;
        }

        filter.alwaysShow.add(dialogId);

        TLRPC.TL_messages_updateDialogFilter req = new TLRPC.TL_messages_updateDialogFilter();
        req.id = folderId;
        req.filter = new TLRPC.TL_dialogFilter();
        req.filter.id = folderId;
        req.filter.title = filter.name;

        req.filter.include_peers = new ArrayList<>();
        for (int i = 0; i < filter.alwaysShow.size(); i++) {
            long did = filter.alwaysShow.get(i);
            TLRPC.InputPeer peer = messagesController.getInputPeer(did);
            if (peer != null) {
                req.filter.include_peers.add(peer);
            }
        }

        if (filter.neverShow != null && !filter.neverShow.isEmpty()) {
            req.filter.exclude_peers = new ArrayList<>();
            for (int i = 0; i < filter.neverShow.size(); i++) {
                long did = filter.neverShow.get(i);
                TLRPC.InputPeer peer = messagesController.getInputPeer(did);
                if (peer != null) {
                    req.filter.exclude_peers.add(peer);
                }
            }
        }

        req.filter.flags = filter.flags;

        getConnectionsManager().sendRequest(req, (response, error) -> {
            AndroidUtilities.runOnUIThread(() -> {
                if (error == null) {
                    getNotificationCenter().postNotificationName(NotificationCenter.dialogFiltersUpdated);
                } else {
                    filter.alwaysShow.remove(dialogId);
                }
            });
        });
    }
    // ===== END MODIFICATION =====
"""

        # Insert before the last closing brace
        last_brace = content.rfind("}")
        if last_brace == -1:
            print("ERROR: Could not find insertion point")
            shutil.copy2(backup_file, chat_activity)
            sys.exit(1)

        content = content[:last_brace] + new_methods + content[last_brace:]
        print("Added new methods")

        with open(chat_activity, "w", encoding="utf-8") as f:
            f.write(content)

        print("Modification successful!")

    # ============================================================
    # Verification
    # ============================================================
    print("")
    print("=== Modification Complete ===")
    print(f"Backup saved to: {backup_file}")
    print("")
    print("Verifying changes...")

    with open(chat_activity, "r", encoding="utf-8") as f:
        final_content = f.read()

    if "showFolderSelectionDialog" in final_content:
        print("  [OK] showFolderSelectionDialog method found")
    else:
        print("  [FAIL] showFolderSelectionDialog method NOT found")

    if "addDialogToFolder" in final_content:
        print("  [OK] addDialogToFolder method found")
    else:
        print("  [FAIL] addDialogToFolder method NOT found")

    with open(strings_xml, "r", encoding="utf-8") as f:
        final_strings = f.read()

    if 'name="AddToFolder"' in final_strings:
        print("  [OK] String resources added")
    else:
        print("  [FAIL] String resources NOT found")

    print("")
    print("To restore from backup:")
    print(f"  cp {backup_file} {chat_activity}")


if __name__ == "__main__":
    project_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    main(project_dir)