import pygame
from pygame.locals import *
import os
import time

IMG_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "img")
POWER_BTN = os.path.join(IMG_DIR, "power-btn.png")
TEMP_BADGE = os.path.join(IMG_DIR, "temp-badge.png")


WHITE = (255, 255, 255)
GREY = (200, 200, 200)
BLACK = (0, 0, 0)


class ImageButton(object):
    def __init__(self, position, image_filename):
        self.Image = pygame.image.load(image_filename)
        self.Position = position
        self.Rect = self.Image.get_rect().move(position)

    def render(self, surface, pos=None):
        if pos:
            self.Position = pos
            self.Rect = self.Rect.move(pos)

        surface.blit(self.Image, self.Position)

    def handleClick(self, event_pos):
        print("Rect: %s, pos: %s"%(self.Rect, event_pos))
        if self.Rect.collidepoint(event_pos):
            self.callback()

    def callback(self):
        return


class PowerButton(ImageButton):
    def __init__(self, position):
        ImageButton.__init__(self, position, POWER_BTN)

    def callback(self):
        print("POWER BUTTON PRESSED")


class TempAndHumidity(object):
    def __init__(self, position, data_func, data_args):
        self.Position = position
        self.DataFunc = data_func
        self.DataArgs = data_args

        self.Image = pygame.image.load(TEMP_BADGE).convert_alpha()
        # self.Image.set_colorkey((0, 0, 0))
        # pygame.Surface.convert_alpha(self.Image)
        self.Font = pygame.font.SysFont("avenir", 20)
        self.updateValues()

    def updateValues(self):
        if self.DataFunc:
            self.Temp, self.Humidity = self.DataFunc(*self.DataArgs)
        else:
            # temp = "%d F"%(t)
            # humidity = "%d %"%(h)
            self.Temp = "76 F"
            self.Humidity = "66 %"

    def render(self, surface):
        self.updateValues()
        size = self.Image.get_rect().size
        badge_surface = pygame.surface.Surface(size, pygame.SRCALPHA)
        badge_surface.blit(self.Image, (0,0))


        temp_surface = self.Font.render(self.Temp, 1, BLACK)
        humidity_surface = self.Font.render(self.Humidity, 1, BLACK)
        # TODO: don't hard code the positions
        badge_surface.blit(temp_surface, (11, 7))
        badge_surface.blit(humidity_surface, (10, 26))

        surface.blit(badge_surface, self.Position)


class StartStopButton(object):
    def __init__(self, position, start_callback, stop_callback):
        self.Position = position
        self.On = False
        self.StartCallback = start_callback
        self.StopCallback = stop_callback
        self.Font = pygame.font.SysFont("avenir", 48)

    def render(self, surface):
        if self.On:
            text = self.Font.render(" STOP ", 1, BLACK)
        else:
            text = self.Font.render(" START ", 1, BLACK)

        size = text.get_rect().size
        base_surface = pygame.surface.Surface(size, pygame.SRCALPHA)
        base_surface.blit(text, (0,0))
        border = 2
        # top line
        pygame.draw.rect(base_surface, BLACK, [0, 0, size[0], border])
        # left line
        pygame.draw.rect(base_surface, BLACK, [0, 0, border, size[1]])
        # bottom line
        pygame.draw.rect(base_surface, BLACK, [0, size[1]-border, size[0], size[1]])
        # right line
        pygame.draw.rect(base_surface, BLACK, [size[0]-border, 0, size[0], size[1]])

        surface.blit(base_surface, self.Position)
        self.Rectangle = pygame.Rect(self.Position[0], self.Position[1], size[0], size[1])

    def handleClick(self, event_pos):
        print("Rect: %s, pos: %s"%(self.Rectangle, event_pos))
        if self.Rectangle.collidepoint(event_pos):
            if self.On:
                self.On = False
                self.StopCallback()
            else:
                self.On = True
                self.StartCallback()


class TimerControl(object):
    def __init__(self, position):
        self.Position = position
        self.StartTime = None
        self.Running = False
        self.Font = pygame.font.SysFont("avenir", 48)

    def start(self):
        self.StartTime = time.time()
        self.Running = True

    def stop(self):
        self.StartTime = None
        self.Running = False

    def render(self, surface):
        if self.Running:
            elapsed = time.time() - self.StartTime
        else:
            elapsed = 0

        m, seconds = divmod(elapsed, 60)
        hours, minutes = divmod(m, 60)
        text = self.Font.render(" %02d:%02d:%02d "%(hours, minutes, seconds), 1, BLACK)
        size = text.get_rect().size
        base_surface = pygame.surface.Surface(size, pygame.SRCALPHA)
        base_surface.blit(text, (0,0))
        border = 2
        # top line
        pygame.draw.rect(base_surface, BLACK, [0, 0, size[0], border])
        # left line
        pygame.draw.rect(base_surface, BLACK, [0, 0, border, size[1]])
        # bottom line
        pygame.draw.rect(base_surface, BLACK, [0, size[1]-border, size[0], size[1]])
        # right line
        pygame.draw.rect(base_surface, BLACK, [size[0]-border, 0, size[0], size[1]])

        surface.blit(base_surface, self.Position)
        self.Rectangle = base_surface.get_rect()