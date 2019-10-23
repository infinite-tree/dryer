import json
import math
import os
import pyenttec as dmx
import pygame
from pygame.locals import *
import time

# local imports
import widgets


PRODUCTION = os.getenv("PRODUCTION")
CONFIG_FILE = os.path.expanduser("~/.dmx.config")
MANIFOLD_BG = os.path.join(widgets.IMG_DIR, "manifold.png")
BLOWER_BG = os.path.join(widgets.IMG_DIR, "blower.png")

# Channel Mapping
# 1. Lower Damper
# 2. Upper Damper
# 3. Blower VFD
# 4. Exhaust Damper
LOWER_DAMPER = '0'
UPPER_DAMPER = '1'
BLOWER_VFD = '2'
EXHAUST_DAMPER = '3'

UPDATE_DELAY = 5

def scale(x, in_min, in_max, out_min, out_max):
    return (x-in_min) * (out_max - out_min) / (in_max - in_min) + out_min


class FakeDMX(object):
    def __init__(self):
        self.dmx_frame = {}

    def render(self):
        print("DMX_FRAME: %s"%self.dmx_frame)
        self.dmx_frame = {}
        return


class DMXWrapper(object):
    def __init__(self, log):
        self.Log = log
        if PRODUCTION:
            self.Dmx = dmx.DMXConnection('/dev/ttyUSB0')
        else:
            self.Dmx = FakeDMX()

        self.Config = {
            LOWER_DAMPER: 255,
            UPPER_DAMPER: 255,
            BLOWER_VFD: 0,
            EXHAUST_DAMPER: 0
        }
        self.Pending = dict(self.Config)

        if os.path.isfile(CONFIG_FILE):
            self.Log.info("Loading DMX config from %s"%CONFIG_FILE)
            with open(CONFIG_FILE) as f:
                self.Config = json.loads(f.read())
                self.Pending = dict(self.Config)
                # FIXME: keys are strings
        else:
            self.Log.info("Creating DMX config file: %s"%CONFIG_FILE)
            # Force a write
            self.setValue(0,0)

        # self.update()

    def setValue(self, channel, value):
        self.Config[channel] = int(value)
        self.Pending[channel] = int(value)

        with open(CONFIG_FILE, "w") as f:
            f.write(json.dumps(self.Config,
                               sort_keys=True,
                               indent=4, separators=(',', ': ')))

    def getValue(self, channel):
        return self.Config.get(channel, 0)

    def update(self):
        if self.Pending:
            for k, v in self.Pending.items():
                self.Log.info("Settings DMX channel %s to %d" % (k, v))
                self.Dmx.dmx_frame[int(k)] = v

            self.Dmx.render()
            self.Pending = {}

    # def tempUpdate(self, channel, value):
    #     self.Dmx.dmx_frame[int(channel)] = int(value)
    #     self.Dmx.render()


class ManifoldControl(object):
    def __init__(self, position, log, dmx_connection, upper_channel, lower_channel, update_handler):
        self.Position = position
        self.Log = log
        self.Dmx = dmx_connection
        self.UpperChannel = upper_channel
        self.LowerChannel = lower_channel
        self.UpdateHandler = update_handler

        self.Background = pygame.image.load(MANIFOLD_BG).convert_alpha()
        self.Size = self.Background.get_size()
        self.Font = pygame.font.SysFont("avenir", 36)
        self.Text = self.Font.render("Manifold", 1, widgets.BLACK)
        self.TextSize = self.Text.get_size()


        self.TopLimitY = self.TextSize[1]+20
        self.BottomLimitY = self.Size[1]-25
        self.Dragging = False
        self.SliderOffset = 0

    def adjustDampers(self, relative_slider_pos):
        if relative_slider_pos == 50:
            self.Dmx.setValue(self.UpperChannel, 255)
            self.Dmx.setValue(self.LowerChannel, 255)
        elif relative_slider_pos > 50:
            self.Dmx.setValue(self.UpperChannel, 255)
            new_pos = 255 - scale(relative_slider_pos, 50, 100, 0, 255)
            self.Dmx.setValue(self.LowerChannel, new_pos)
        elif relative_slider_pos < 50:
            self.Dmx.setValue(self.LowerChannel, 255)
            new_pos = scale(relative_slider_pos, 0, 50, 0, 255)
            self.Dmx.setValue(self.UpperChannel, new_pos)

        self.UpdateHandler()

    def setSliderPos(self, y_pos):
        # print("TOP: %d, BOTTOM: %d"%(self.TopLimitY, self.BottomLimitY))
        rel_y = scale(y_pos, self.TopLimitY, self.BottomLimitY, 0, 100)
        # invert for slider
        rel_y = 100 - rel_y
        self.adjustDampers(rel_y)

    def getRelativeSliderPos(self):
        upper = self.Dmx.getValue(self.UpperChannel)
        lower = self.Dmx.getValue(self.LowerChannel)
        if upper == 255 and lower == 255:
            return 50
        elif upper == 255 and lower < 255:
            # Slider shold be above the mid point
            return 100 - scale(lower, 0, 255, 0, 50)
        elif lower == 255 and upper < 255:
            # Slider should be below the mid point
            return scale(upper, 0, 255, 0, 50)
        else:
            self.Log.error("Unknown Manifold positions. Lower: %d, Upper: %d"%(lower, upper))
            return 50

    def getPhysicalSliderPos(self):
        y = 100 - self.getRelativeSliderPos()
        # print("Relative POS: %d"%y)
        pos = int(scale(y, 0, 100, self.TopLimitY, self.BottomLimitY))
        # print("Physical POS: %d: %d - %d"%(pos, self.TopLimitY, self.BottomLimitY))
        return pos

    def handleEvent(self, event):
        if hasattr(event, 'pos'):
            event_pos = (event.pos[0]-self.Position[0], event.pos[1] - self.Position[1])

        if event.type == MOUSEBUTTONDOWN:
            if self.Dot.collidepoint(event_pos):
                self.Dragging = True
                self.SliderOffset = self.Dot.y - event_pos[1]
                # print("SLIDER OFFSET: %d"%self.SliderOffset)
                return True
        if event.type == MOUSEBUTTONUP:
            self.Dragging = False
            return True
        if event.type == MOUSEMOTION and self.Dragging:
            new_pos = min(self.BottomLimitY, event_pos[1] + self.SliderOffset)
            new_pos = max(self.TopLimitY, new_pos)
            self.setSliderPos(new_pos)
            return True
        return False

    def render(self, surface):
        base_surface = pygame.surface.Surface(self.Size, pygame.SRCALPHA)
        base_surface.blit(self.Background, (0,0))

        base_surface.blit(self.Text, (self.Size[0]/2 - self.TextSize[0]/2, 10))
        mid = (self.BottomLimitY - self.TopLimitY)/2 + self.TopLimitY
        pygame.draw.line(base_surface,
                         widgets.BLACK,
                         (self.Size[0]-30, self.TopLimitY),
                         (self.Size[0]-30, self.BottomLimitY),
                         2)
        pygame.draw.line(base_surface,
                         widgets.BLACK,
                         (self.Size[0]-30-25, self.TopLimitY),
                         (self.Size[0]-5, self.TopLimitY),
                         2)
        pygame.draw.line(base_surface,
                         widgets.BLACK,
                         (self.Size[0]-30-25, mid),
                         (self.Size[0]-5, mid),
                         1)
        pygame.draw.line(base_surface,
                         widgets.BLACK,
                         (self.Size[0]-30-25, self.BottomLimitY),
                         (self.Size[0]-5, self.BottomLimitY),
                         2)

        # Draw Position
        y_pos = self.getPhysicalSliderPos()
        self.Dot = pygame.draw.circle(base_surface,
                                      widgets.BLACK,
                                      (self.Size[0]-30, y_pos),
                                      20)

        surface.blit(base_surface, self.Position)
        return


class BlowerControl(object):
    def __init__(self, position, log, dmx_connection, channel, update_handler):
        self.Position = position
        self.Log = log
        self.Dmx = dmx_connection
        self.Channel = channel
        self.UpdateHandler = update_handler

        self.Background = pygame.image.load(BLOWER_BG).convert_alpha()
        self.Size = self.Background.get_size()
        self.Font = pygame.font.SysFont("avenir", 36)
        self.Text = self.Font.render("Blower", 1, widgets.BLACK)
        self.TextSize = self.Text.get_size()

        self.LineEnd = (self.Size[0]-180, self.Size[1]-20)
        self.ControlRadius = 115
        self.AngleLimit = (3.6, 4.9)
        self.BlowerLimit = (0, 255)

        self.UpButton = widgets.UpButton((self.Size[0]-55, 60), self.handleUp)
        self.DownButton = widgets.DownButton((self.Size[0]-55, self.Size[1]-60), self.handleDown)
        self.Increment = 13

    def getControlPoint(self):
        value = float(self.Dmx.getValue(self.Channel))
        # scale 0-255 to degrees in radians
        angle = scale(value, 0.0, 255.0, self.AngleLimit[0], self.AngleLimit[1])
        x = self.LineEnd[0] + (self.ControlRadius * math.cos(angle))
        y = self.LineEnd[1] + (self.ControlRadius * math.sin(angle))
        return (int(x),int(y))

    def handleUp(self):
        v = self.Dmx.getValue(self.Channel)
        v = min(self.BlowerLimit[1], v+self.Increment)
        self.Dmx.setValue(self.Channel, v)
        self.UpdateHandler()

    def handleDown(self):
        v = self.Dmx.getValue(self.Channel)
        v = max(self.BlowerLimit[0], v-self.Increment)
        self.Dmx.setValue(self.Channel, v)
        self.UpdateHandler()

    def handleEvent(self, event):
        if hasattr(event, 'pos'):
            event_pos = (event.pos[0]-self.Position[0],
                         event.pos[1] - self.Position[1])

        if event.type == MOUSEBUTTONDOWN:
            if self.UpButton.handleClick(event_pos):
                return True
            if self.DownButton.handleClick(event_pos):
                return True
        return False

    def render(self, surface):
        base_surface = pygame.surface.Surface(self.Size, pygame.SRCALPHA)
        base_surface.blit(self.Background, (0,0))

        base_surface.blit(self.Text, (self.Size[0]/2 - self.TextSize[0]/2, 10))
        zero = self.Font.render("0", 1, widgets.BLACK)
        hundred = self.Font.render("100", 1, widgets.BLACK)
        base_surface.blit(zero, (self.Size[0]/2 - 90, self.Size[1]-zero.get_size()[1]))
        base_surface.blit(hundred, (self.Size[0]-125, 100))

        # draw buttons
        self.UpButton.render(base_surface)
        self.DownButton.render(base_surface)

        # draw line control
        pos = self.getControlPoint()
        pygame.draw.line(base_surface,
                         widgets.BLACK,
                         self.LineEnd,
                         pos,
                         8)
        pygame.draw.circle(base_surface,
                           widgets.BLACK,
                           pos,
                           25)

        surface.blit(base_surface, self.Position)
        return


class RecirculationControl(object):
    def __init__(self, position, log, dmx_connection, channel, update_handler):
        self.Position = position
        self.Log = log
        self.Dmx = dmx_connection
        self.Channel = channel
        self.UpdateHandler = update_handler

        self.Size = (400,240)
        self.Font = pygame.font.SysFont("avenir", 36)
        self.Text = self.Font.render("Recirculation", 1, widgets.BLACK)
        self.TextSize = self.Text.get_size()

        self.LineEnd = (self.Size[0]-180, self.Size[1]-20)
        self.ControlRadius = 115
        self.AngleLimit = (3.6, 4.9)
        self.BlowerLimit = (0, 255)

        self.UpButton = widgets.UpButton((self.Size[0]-55, 60), self.handleUp)
        self.DownButton = widgets.DownButton((self.Size[0]-55, self.Size[1]-60), self.handleDown)
        self.Increment = 13

    def handleUp(self):
        v = self.Dmx.getValue(self.Channel)
        v = min(self.BlowerLimit[1], v+self.Increment)
        self.Dmx.setValue(self.Channel, v)
        self.UpdateHandler()

    def handleDown(self):
        v = self.Dmx.getValue(self.Channel)
        v = max(self.BlowerLimit[0], v-self.Increment)
        self.Dmx.setValue(self.Channel, v)
        self.UpdateHandler()

    def handleEvent(self, event):
        if hasattr(event, 'pos'):
            event_pos = (event.pos[0]-self.Position[0],
                         event.pos[1] - self.Position[1])

        if event.type == MOUSEBUTTONDOWN:
            if self.UpButton.handleClick(event_pos):
                return True
            if self.DownButton.handleClick(event_pos):
                return True
        return False

    def renderWedge(self, surface, center, radius, start_angle, stop_angle):
        p = [(center[0], center[1])]
        for n in range(start_angle, stop_angle):
            x = center[0] + int(radius*math.cos(n*math.pi/180))
            y = center[1]+int(radius*math.sin(n*math.pi/180))
            p.append((x, y))
        p.append((center[0], center[1]))

        # Draw pie segment
        if len(p) > 2:
            pygame.draw.polygon(surface, (0, 0, 0), p)

    def render(self, surface):
        base_surface = pygame.surface.Surface(self.Size)
        pygame.draw.rect(base_surface, widgets.WHITE,
                         (0, 0, self.Size[0], self.Size[1]))

        base_surface.blit(self.Text, (self.Size[0]/2 - self.TextSize[0]/2, 10))

        center = (int(self.Size[0]/2), int(self.Size[1]/2)+20)
        radius = 75
        pygame.draw.circle(base_surface, widgets.BLACK, center, radius, 2)

        v = self.Dmx.getValue(self.Channel)
        angle = int(scale(255-v, 0, 255, 0, 180))

        # draw buttons
        self.UpButton.render(base_surface)
        self.DownButton.render(base_surface)

        # draw line control
        self.renderWedge(base_surface, center, radius, 0, angle)
        self.renderWedge(base_surface, center, radius, 180, 180+angle)

        surface.blit(base_surface, self.Position)
        return


class Control(object):
    def __init__(self, log, screen, return_handler):
        self.Log = log
        self.Screen = screen
        self.Size = self.Screen.get_size()
        self.ReturnHandler = return_handler

        self.Dmx = DMXWrapper(self.Log)
        self.LastUpdate = time.time()
        self.Running = False

        self.handleStop()

        self.ReturnButton = widgets.ReturnButton((self.Size[0]-55, 5), self.handleReturn)
        self.ManifoldControl = ManifoldControl((0, 0), self.Log, self.Dmx, UPPER_DAMPER, LOWER_DAMPER, self.updateDmx)
        self.BlowerControl = BlowerControl((0, self.Size[1]/2+1), self.Log, self.Dmx, BLOWER_VFD, self.updateDmx)
        self.RecirculationControl = RecirculationControl((self.Size[0]/2+1, self.Size[1]/2+1), self.Log, self.Dmx, EXHAUST_DAMPER, self.updateDmx)

    def handleStart(self):
        self.Running = True
        self.Log.info("Starting Controls")
        # HACK/FIXME
        self.Dmx.Pending = dict(self.Dmx.Config)
        self.Dmx.update()
        self.LastUpdate = time.time()

    def handleStop(self):
        self.Running = False
        self.Log.info("Stopping Controls")
        # HACK/FIXME
        self.Dmx.Dmx.dmx_frame[int(BLOWER_VFD)] = 0
        self.Dmx.Dmx.render()

    def updateDmx(self):
        now = time.time()
        if self.Running and now - self.LastUpdate > UPDATE_DELAY:
            self.Dmx.update()
            self.LastUpdate = now

    def handleReturn(self):
        # flush any pending dmx updates
        if self.Running:
            self.Dmx.update()
        self.ReturnHandler()

    def handleEvent(self, event):
        if self.ManifoldControl.handleEvent(event):
            return True
        if self.BlowerControl.handleEvent(event):
            return True
        if self.RecirculationControl.handleEvent(event):
            return True

        if event.type == MOUSEBUTTONDOWN:
            self.ReturnButton.handleClick(event.pos)
        return True

    def render(self):
        surface = pygame.surface.Surface(self.Size)
        pygame.draw.rect(surface, widgets.WHITE, (0,0,self.Size[0],self.Size[1]))
        self.ReturnButton.render(surface)
        self.ManifoldControl.render(surface)
        self.BlowerControl.render(surface)
        self.RecirculationControl.render(surface)

        self.Screen.blit(surface, (0,0))
