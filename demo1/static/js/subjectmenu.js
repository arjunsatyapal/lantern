// Copyright 2010 Google Inc. All Rights Reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

/**
 * @fileoverview Menu for selection of subject item.
 */
goog.provide('lantern.ui.SubjectMenuButton');
goog.provide('lantern.ui.SubjectMenu');

goog.require('goog.structs');
goog.require('goog.Timer');
goog.require('goog.ui.Component');
goog.require('goog.ui.Component.EventType');
goog.require('goog.ui.Menu');
goog.require('goog.ui.MenuButton');
goog.require('goog.ui.MenuItem');
goog.require('goog.ui.MenuSeparator');
goog.require('goog.ui.SubMenu');

goog.require('lantern.subject.SubjectItem');
goog.require('lantern.subject.SubjectProvider');



/**
 * Menu button to pop up Subject Taxonomy menu.  Overrides the action
 * handler to not pop down the menu prematurely.
 *
 * @param {goog.ui.COntrolContent} content Text caption or existing DOM
 *     structure to display as the button's caption (if any).
 * @param {goog.dom.ButtonRenderer=} opt_renderer Renderer used to render or
 *     decorate the menu button; defaults to
 *     {@link goog.uji.MenuButtonRenderer}.
 * @param {goog.dom.DomHelper=} opt_domHelper Optional DOM helper, used for
 *     document interaction.
 * @constructor
 * @extends {goog.ui.MenuButton}
 */
lantern.ui.SubjectMenuButton = function(
    content, opt_renderer, opt_domHelper) {
  goog.ui.MenuButton.call(this, content, null, opt_renderer, opt_domHelper);
};
goog.inherits(lantern.ui.SubjectMenuButton, goog.ui.MenuButton);


/**
 * @inheritDoc
 */
lantern.ui.SubjectMenuButton.prototype.handleMenuAction = function(e) {
  // Override to do nothing.
};


/**
 * Subject menu that presents two-level menus for the current root
 * subject. It is used for presenting the taxonomy of subjects.
 *
 * <p>Behavior:
 * <ul>
 *  <li>The first level of menus are SubMenu that expand into sub menus on
 *   hover.
 *  <li>When an element in the second level of menu is selected, the sub-menu
 *   replaces the main menu with the selected menu remaining high-lighted and
 *   expanded to the next level of menu.
 *  <li>When a "leaf" subject is selected, the goog.ui.Component.ACTION event
 *   is dispatched to listeners.
 * </ul>
 *
 * TODO(vchen): Figure out how to manage the CSS styles to control look/feel.
 *
 * @param {lantern.ui.SubjectProvider} provider A data provider of
 *     subject items.
 * @param {good.ui.MenuButton} opt_menuButton Optional menu button to attach
 *     this menu. If not specified, the top-level menu is always shown.
 * @param {goog.dom.DomHelper} opt_domHelper Optional DOM helper.
 * @constructor
 * @extends {goog.ui.Component}
 */
lantern.ui.SubjectMenu = function(provider, opt_menuButton, opt_domHelper) {
  goog.ui.Component.call(this, opt_domHelper);

  /**
   * The data provider of subject items.
   * @type {lantern.subject.SubjectProvider}
   * @private
   */
  this.subjectProvider_ = provider;

  /**
   * Current root subject ID. null means root of all subjects.
   * @type {string?}
   * @private
   */
  this.currentRootId_ = null;

  /**
   * Currently selected subject. This is used when the menu is structure is
   * changed to highlight the selected subject.
   * @type {lantern.subject.SubjectItem?}
   * @private
   */
  this.currentSubject_ = null;

  /**
   * Main menu.
   * @type {goog.ui.Menu}
   * @private
   */
  this.menu_;

  /**
   * Optional menu button to attach this menu.
   * @type {goog.ui.MenuButton}
   * @private
   */
  this.menuButton_ = opt_menuButton;

  /**
   * Event handler helper.
   * @type {goog.events.EventHandler}
   * @private
   */
  this.eh_ = new goog.events.EventHandler(this);

  /**
   * Whether menu should be opened.  Only applicable when menu button is
   * used.
   *
   * @type {boolean}
   * @private
   */
  this.isOpen_ = false;
};
goog.inherits(lantern.ui.SubjectMenu, goog.ui.Component);


/**
 * Default CSS class to att to the root element.
 * @type {string}
 */
lantern.ui.SubjectMenu.CSS_CLASS = goog.getCssName('lantern-subject');


/**
 * Left-facing arror.
 * @type {string}
 * @private
 */
lantern.ui.SubjectMenu.LEFT_ARROW_ = '\u25C4';


/**
 * Right-facing arror.
 * @type {string}
 * @private
 */
lantern.ui.SubjectMenu.RIGHT_ARROW_ = '\u25BA';


/**
 * Text for the special menu item for going to the root/top.
 * @type {string}
 */
lantern.ui.SubjectMenu.MENU_ITEM_TOP = "Top";


/**
 * Text for the special menu item for going back one level.
 * @type {string}
 */
lantern.ui.SubjectMenu.MENU_ITEM_BACK = "Back";


/**
 * Returns the underlying menu.
 * @return {goog.ui.Menu}
 */
lantern.ui.SubjectMenu.prototype.getMenu = function() {
  return this.menu_;
};


/**
 * Triggers loading of subjects started with the specified root subject. It is
 * expected that the SubjectProvider will load sufficient data for displaying
 * two levels of menus, starting with the children of the specified root
 * subject.
 *
 * <p>When data is loaded, the SubjectProvider will fire either the DATA_READY
 * or DATA_ERROR event.
 *
 * @param {string?} rootId The ID of the root subject, where null means the
 *     root subjects.
 * @param {lantern.subject.SubjectItem} opt_subject Optional argument specifying
 *     the currently selected subject that triggered this request.
 */
lantern.ui.SubjectMenu.prototype.loadSubjects_ = function(rootId, opt_subject) {
  this.currentRootId_ = rootId;
  this.currentSubject_ = opt_subject;
  this.subjectProvider_.loadSubjects(rootId);
};


/**
 * Handler that is called when menu item selected. The handler performs the
 * following:
 * <ul>
 *  <li>If TOP is selected, replace the menu with root menu.
 *  <li>If BACK is selected, replace the menu with parent of the current root
 *    subject.
 *  <li>Otherwise, replace the menu with the parent of the selected subject,
 *    exposing the next level of menus.
 *  <li>If the item is a leaf entry, the event will be forwarded as an event
 *    of this menu.
 * </ul>
 *
 * @param {goog.events.Event} e Event object representing the selection event.
 */
lantern.ui.SubjectMenu.prototype.onSelection_ = function(e) {
  var subject = e.target.getValue();
  var parent;
  if (subject == lantern.ui.SubjectMenu.MENU_ITEM_TOP) {
    parent = null;
    subject = null;
    this.isOpen_ = true;
  } else if (subject == lantern.ui.SubjectMenu.MENU_ITEM_BACK) {
    parent = this.subjectProvider_.getParent(this.currentRootId_);
    subject = null;
    this.isOpen_ = true;
  } else {
    parent = this.subjectProvider_.getParent(subject.id);
    if (subject.isLeaf) {
      // Forward selection of leafs to any listeners.
      this.dispatchEvent(e);
      this.isOpen_ = false;
    } else {
      e.stopPropagation();
      this.isOpen_ = true;
    }
  }
  this.loadSubjects_(parent ? parent.id : null, subject);
};


/**
 * Handler called when fresh data is loaded.  It calls setRootSubject_() to
 * rebuild the menus at the current root subject.
 *
 * @param {goog.events.Event} e Event object representing the data-ready
 *     event.
 */
lantern.ui.SubjectMenu.prototype.onDataReady_ = function(e) {
  this.setRootSubject_(this.currentRootId_, this.currentSubject_);
};


/**
 * Sets the root subject, rebuilding the menus from the specified subject; the
 * main menu are the child subjects of the specified root subject. This
 * is expected to be called when the underlying data is ready.
 *
 * @param {string?} rootId The ID of the subject item that is the current root
 *     of the menu.  It may be null to indicate root of the subject hierarchy.
 * @param {lantern.subject.SubjectItem?} currentSubject The currently selected
 *     subject that should be highlighted after the menus have been rebuilt.
 *     If null, there is no current selection.
 */
lantern.ui.SubjectMenu.prototype.setRootSubject_ = function(
    rootId, currentSubject) {

  var oldmenu = this.menu_;

  // Construct a new menu.
  var menu = new goog.ui.Menu();
  this.buildMenu_(menu, this.currentRootId_, true);
  if (this.menuButton_) {
    this.menuButton_.setMenu(menu);
    if (this.isOpen_) {
      this.menuButton_.showMenu();
    }
  } else {
    menu.render(this.element_);
  }

  // Replace the old menu before disposing of the old menu.
  this.menu_ = menu;

  this.eh_.unlisten(oldmenu, goog.ui.Component.EventType.ACTION,
                    this.onSelection_);
  oldmenu.dispose();

  // Set up listener for new menu.
  this.eh_.listen(menu, goog.ui.Component.EventType.ACTION,
                  this.onSelection_);

  // Open the submenu, if appropriate.
  if (currentSubject && !currentSubject.isLeaf) {
    var menuItems = this.menu_.getItems();
    var numItems = menuItems.length;
    for (var i = 0; i < numItems; ++i) {
      if (menuItems[i].getModel().id == currentSubject.id) {
        this.menu_.setHighlighted(menuItems[i]);
        if (menuItems[i].showSubMenu) {
          menuItems[i].showSubMenu();
        }
        break;
      }
    }
  }
};


/**
 * Builds one layer of the menu. Recursive.
 *
 * @param {goog.ui.Menu} menu The menu to be built.
 * @param {string} subjectId The ID of the subject whose children are to be
 *     added to the menu.
 * @param {boolean} hasSubMenu Whether the menu has sub menus.
 */
lantern.ui.SubjectMenu.prototype.buildMenu_ = function(
    menu, subjectId, hasSubMenu) {
  var items = this.subjectProvider_.getChildSubjects(subjectId);
  var numItems = items ? items.length : 0;

  for (var i = 0; i < numItems; ++i) {
    var item = items[i];
    var menuItem;
    if (hasSubMenu && !item.isLeaf) {
      menuItem = new goog.ui.SubMenu(item.displayText, item);
      this.buildMenu_(menuItem.getMenu(), item.id, false);
    } else {
      menuItem = new goog.ui.MenuItem(item.displayText, item);
      menuItem.addClassName(goog.getCssName(
          lantern.ui.SubjectMenu.CSS_CLASS, 'submenu'));
    }
    menuItem.addClassName(goog.getCssName(
        lantern.ui.SubjectMenu.CSS_CLASS, 'menu'));
    menu.addItem(menuItem);
    if (!hasSubMenu && !item.isLeaf) {
      this.addArrow_(menuItem, false /* not backwards arrow */);
    }
  }
  if (hasSubMenu && subjectId != null) {
    menu.addItem(new goog.ui.MenuSeparator());

    goog.array.forEach([lantern.ui.SubjectMenu.MENU_ITEM_TOP,
                        lantern.ui.SubjectMenu.MENU_ITEM_BACK],
        function(label) {
          // Create contents with a left arrow.
          var menuItem = new goog.ui.MenuItem(label);
          menuItem.setModel(label);
          menuItem.addClassName(goog.getCssName(
              lantern.ui.SubjectMenu.CSS_CLASS, 'menu'));
          menuItem.addClassName(goog.getCssName(
              lantern.ui.SubjectMenu.CSS_CLASS, 'submenu'));
          menu.addItem(menuItem);
          this.addArrow_(menuItem, true /* is backwards arrow */);
        }, this);
  }
};


/**
 * @inheritDoc
 */
lantern.ui.SubjectMenu.prototype.createDom = function() {
  this.decorateInternal(this.getDomHelper().createElement('div'));
};


/**
 * @inheritDoc
 */
lantern.ui.SubjectMenu.prototype.render = function(el) {
  lantern.ui.SubjectMenu.superClass_.render.call(this, el);
  if (this.menuButton_) {
    this.menuButton_.render(el);
  }
};


/**
 * @inheritDoc
 */
lantern.ui.SubjectMenu.prototype.decorateInternal = function(element) {
  this.element_ = element;

  goog.dom.removeChildren(element);

  // Construct, but this menu is empty and not really used. The real menu
  // is built only after data is loaded.
  this.menu_ = new goog.ui.Menu();
  if (this.menuButton_) {
    this.menuButton_.setMenu(this.menu_);
  } else {
    this.menu_.decorate(element);
  }

  // Bootstrap by loading the root subjects.
  goog.Timer.callOnce(goog.bind(this.loadSubjects_, this, null), 10);
};


/**
 * @inheritDoc
 */
lantern.ui.SubjectMenu.prototype.enterDocument = function() {
  lantern.ui.SubjectMenu.superClass_.enterDocument.call(this);

  if (this.menuButton_) {
    //    this.menuButton_.enterDocument();
  } else {
    this.menu_.enterDocument();
  }

  // Set up event handlers
  this.eh_.listen(this.menu_, goog.ui.Component.EventType.ACTION,
                  this.onSelection_);
  this.eh_.listen(this.subjectProvider_,
                  lantern.subject.SubjectProvider.EventType.DATA_READY,
                  this.onDataReady_);
};


/**
 * @inheritDoc
 */
lantern.ui.SubjectMenu.prototype.exitDocument = function() {
  lantern.ui.SubjectMenu.superClass_.exitDocument.call(this);

  this.eh_.removeAll();
  if (this.menu_) {
    this.menu_.exitDocument();
  }
  if (this.menuButton_) {
    this.menuButton_.exitDocument();
  }
};


/**
 * @inheritDoc
 */
lantern.ui.SubjectMenu.prototype.disposeInternal = function() {
  lantern.ui.SubjectMenu.superClass_.disposeInternal.call(this);

  if (this.eh_) {
    this.eh_.dispose();
  }
  if (this.menu_) {
    this.menu_.dispose();
  }
  if (this.menuButton_) {
    this.menuButton_.dispose();
  }
  this.eh_ = null;
  this.menu_ = null;
  this.menuButton_ = null;
};


/**
 * @inheritDoc
 */
lantern.ui.SubjectMenu.prototype.getClassId = function() {
  return 'lantern.ui.SubjectMenu';
};


/**
 * @inheritDoc
 */
lantern.ui.SubjectMenu.prototype.canDecorate = function(existingElement) {
  return existingElement.tagName == 'DIV';
};


/**
 * Adds arrow to the menu item.
 * @param {goog.ui.MenuItem} menuItem the sub-menu that should have the arrow.
 * @param {boolean} isBack If true, points backwards.
 * @private
 */
lantern.ui.SubjectMenu.prototype.addArrow_ = function(menuItem, isBack) {
  var arrow = this.getDomHelper().createDom('span');
  arrow.className = goog.getCssName('goog-submenu-arrow');
  this.setArrowTextContent_(menuItem, arrow, isBack);
  if (isBack) {
    menuItem.getContentElement().insertBefore(
        arrow, menuItem.getContentElement().childNodes[0]);
  } else {
    menuItem.getContentElement().appendChild(arrow);
  }
};


/**
 * Sets the text content of an arrow. Borrowed from goog.ui.SubMenuRenderer.
 *
 * @param {goog.ui.MenuItem} menuItem The sub-menu that should have the arrow.
 * @param {Element} arrow The arrow element.
 * @param {boolean} isBack If true, points backwards.
 * @private
 */
lantern.ui.SubjectMenu.prototype.setArrowTextContent_ = function(
    menuItem, arrow, isBack) {
  // Fix arror RTL
  var leftArrow = lantern.ui.SubjectMenu.LEFT_ARROW_;
  var rightArrow = lantern.ui.SubjectMenu.RIGHT_ARROW_;
  if (menuItem.isRightToLeft()) {
    goog.dom.classes.add(arrow, goog.getCssName('goog-submenu-arrow-rtl'));
    goog.dom.setTextContent(arrow, isBack ? rightArrow : leftArrow);
  } else {
    goog.dom.classes.add(arrow, goog.getCssName('goog-submenu-arrow-ltr'));
    goog.dom.setTextContent(arrow, isBack ? leftArrow : rightArrow);
  }
};
