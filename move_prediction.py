# %%
# Imports
import networkx as nx
import numpy as np
import numpy.typing
from dataclasses import dataclass
import os
import glob
import shutil
from typing import DefaultDict, Iterator, Tuple, TypeVar, Union
import matplotlib.image
import matplotlib.pyplot
from numpy import ndarray
from hoplite.game.terrain import Terrain
from collections import defaultdict
from hoplite.utils import HexagonalCoordinates, hexagonal_distance, hexagonal_neighbors
import hoplite.game.demons
try:
    import hoplite
except ModuleNotFoundError:
    os.chdir("..")
import hoplite.game.state
import hoplite.game.moves
import hoplite.actuator
import itertools
import functools
from operator import methodcaller
# %%
# Main script configuration
OUTPUT_DIRECTORY = "draft/walk"
RECORDINGS_FOLDER = "recordings"
LOG_FILENAME = "game.log"
# %%
# visualize predicted states
# check if one of predicted state matches
# calculate move tree


@dataclass
class Action:
    source: HexagonalCoordinates
    destination: HexagonalCoordinates
    def apply(self,gamestate:hoplite.game.state.GameState):
        return gamestate

    def __hash__(self):
        return hash((self.source, self.destination))


class Wait(Action):
    def __init__(self, position: HexagonalCoordinates):
        super().__init__(position, position)
    def apply(self,gamestate:hoplite.game.state.GameState):
        return gamestate


class Attack(Action):
    def __init__(self, position: HexagonalCoordinates):
        super().__init__(position, position)
    def apply(self,gamestate:hoplite.game.state.GameState):
        return gamestate


class Walk(Action):
    def apply(self,gamestate:hoplite.game.state.GameState):
        gamestate.terrain.demons[self.destination]=gamestate.terrain.demons[self.source]
        gamestate.terrain.demons.pop(self.source)
        return gamestate


class Bomb(Action):
    def apply(self,gamestate:hoplite.game.state.GameState):
        if isinstance((x :=gamestate.terrain.demons[self.source]),hoplite.game.demons.Demolitionist):
            x.throw_bomb()
        gamestate.terrain.bombs.add(self.destination)
        return gamestate

def apply_actions(gamestate:hoplite.game.state.GameState,actions:set[frozenset[Action]]):
    return {functools.reduce(lambda state,action:action.apply(state),action_set,gamestate.copy()) for action_set in actions}



class Demon:
    def __init__(self, position: HexagonalCoordinates) -> None:
        self.position = position

    def get_all_moves(self, _terrain: Terrain):
        return frozenset({Wait(self.position)})

    def get_moves(self, _terrain: Terrain, _collisions: set[HexagonalCoordinates]):
        return frozenset({Wait(self.position)})

    def __hash__(self):
        return hash(self.position)


class Footman(Demon):
    def __init__(self, position: HexagonalCoordinates) -> None:
        super().__init__(position)
        self._stored_moves: dict[HexagonalCoordinates, int] = {}

    def get_stored_moves(self, terrain: Terrain):
        if not self._stored_moves:
            moves: set[HexagonalCoordinates] = {destination
                                                for destination in hexagonal_neighbors(self.position)
                                                if terrain.walkable(destination)}
            moves.add(self.position)
            self._stored_moves = {hex_coord: len(terrain.pathfind(
                hex_coord, terrain.player) or []) for hex_coord in moves}
        return self._stored_moves

    def get_all_moves(self, terrain: Terrain):
        if terrain.player in hexagonal_neighbors(self.position):
            return {Attack(self.position)}
        stored_moves = self.get_stored_moves(terrain)
        filtered_stored_moves = {position for position, path_length in stored_moves.items(
        ) if path_length <= stored_moves[self.position]}
        actions: set[Action] = {Walk(self.position, destination)
                                for destination in filtered_stored_moves if destination not in terrain.demons.keys()}
        actions.add(Wait(self.position))
        return frozenset(actions)

    def get_moves(self, terrain: Terrain, collisions: Union[frozenset[HexagonalCoordinates], set[HexagonalCoordinates]]):
        if terrain.player in hexagonal_neighbors(self.position):
            return frozenset({Attack(self.position)})
        stored_moves = self.get_stored_moves(terrain)
        all_moves_collisionless = dict(
            filter(lambda x: x[0] not in collisions and x[0] not in terrain.demons.keys() or x[0] == self.position, stored_moves.items()))

        prefered = {hex_coord for hex_coord, lenght in all_moves_collisionless.items(
        ) if lenght < stored_moves[self.position]}
        if prefered:
            return frozenset({Walk(self.position, x) for x in prefered})
        secondary = {hex_coord for hex_coord, lenght in all_moves_collisionless.items(
        ) if lenght == self._stored_moves[self.position]}
        return frozenset({Walk(self.position, x) if self.position != x else Wait(self.position) for x in secondary})


def demon_mapper(demon: hoplite.game.demons.Demon, position: HexagonalCoordinates):
    if isinstance(demon, hoplite.game.demons.Footman):
        return Footman(position)
    elif isinstance(demon, hoplite.game.demons.Archer):
        return Archer(position)
    elif isinstance(demon, hoplite.game.demons.Demolitionist):
        return Demolitionist(position,demon.cooldown)
    elif isinstance(demon, hoplite.game.demons.Wizard):
        return Wizard(position,demon.charged_wand)
    raise ValueError("Incorrect hoplite.game.demons.Demon type!")

# functions to define
# moves toward player
# > check if on axis
# > divide by axis

# moves in ring to player
# > same as towards player

# moves toward and in ring to player
# > same as in top

# moves away from player
# > same as in top

# neibours in shooting line
# > iterate through neihbours and check for same coordinates
# > there should be method using 1>=x>=-1

# moves toward in shooting line
# moves in ring in shooting line
# moves away to shooting line


# is in shooting line
# > has one coordinate same as target
def get_hexes_by_axis(source:HexagonalCoordinates,target:HexagonalCoordinates):
    if source.x == target.x:
        if source.y>target.y:
            return 6
        return 0
    if source.x < target.x:
        if source.y < target.y:
            return 1
        if source.y == target.y:
            return 2
        if source.z > target.z:
            return 3
        if source.z == target.z:
            return 4
        return 5
    if source.y > target.y:
        return 7
    if source.y == target.y:
        return 8
    if source.z < target.z:
        return 9
    if source.z == target.z:
        return 10
    return 11
keep_radius_offsets =  np.array([
    {HexagonalCoordinates(-1,1),HexagonalCoordinates(1,0)},
    {HexagonalCoordinates(-1,1),HexagonalCoordinates(1,-1)},
    {HexagonalCoordinates(0,1),HexagonalCoordinates(1,-1)},
    {HexagonalCoordinates(0,1),HexagonalCoordinates(0,-1)},
    {HexagonalCoordinates(1,0),HexagonalCoordinates(0,-1)},
    {HexagonalCoordinates(1,0),HexagonalCoordinates(-1,0)},
    {HexagonalCoordinates(1,-1),HexagonalCoordinates(-1,0)},
    {HexagonalCoordinates(1,-1),HexagonalCoordinates(-1,1)},
    {HexagonalCoordinates(0,-1),HexagonalCoordinates(-1,1)},
    {HexagonalCoordinates(0,-1),HexagonalCoordinates(0,1)},
    {HexagonalCoordinates(-1,0),HexagonalCoordinates(0,1)},
    {HexagonalCoordinates(-1,0),HexagonalCoordinates(1,0)}
    ],dtype=object)

def keep_radius(source:HexagonalCoordinates,target:HexagonalCoordinates):
    result:set[HexagonalCoordinates] = set()
    for x in keep_radius_offsets[get_hexes_by_axis(source,target)]:
        tmp:HexagonalCoordinates = x
        result.add(source+tmp)
    return result
reducing_radius_offsets=  np.array([
    {HexagonalCoordinates(0,1)},
    {HexagonalCoordinates(0,1),HexagonalCoordinates(1,0)},
    {HexagonalCoordinates(1,0)},
    {HexagonalCoordinates(1,0),HexagonalCoordinates(1,-1)},
    {HexagonalCoordinates(1,-1)},
    {HexagonalCoordinates(1,-1),HexagonalCoordinates(0,-1)},
    {HexagonalCoordinates(0,-1)},
    {HexagonalCoordinates(0,-1),HexagonalCoordinates(-1,0)},
    {HexagonalCoordinates(-1,0)},
    {HexagonalCoordinates(-1,0),HexagonalCoordinates(-1,1)},
    {HexagonalCoordinates(-1,1)},
    {HexagonalCoordinates(-1,1),HexagonalCoordinates(0,1)}
    ],dtype=object)
def reduce_radius(source:HexagonalCoordinates,target:HexagonalCoordinates):
    result:set[HexagonalCoordinates] = set()
    for x in reducing_radius_offsets[get_hexes_by_axis(source,target)]:
        tmp:HexagonalCoordinates = x
        result.add(source+tmp)
    return result

reducing_or_keep_radius_offsets=  keep_radius_offsets | reducing_radius_offsets
def reduce_or_keep_radius(source:HexagonalCoordinates,target:HexagonalCoordinates):
    result:set[HexagonalCoordinates] = set()
    for x in reducing_or_keep_radius_offsets[get_hexes_by_axis(source,target)]:
        tmp:HexagonalCoordinates = x
        result.add(source+tmp)
    return result

increase_radius_offsets=  np.array([
    {HexagonalCoordinates(1,-1),HexagonalCoordinates(0,-1),HexagonalCoordinates(-1,0)},
    {HexagonalCoordinates(0,-1),HexagonalCoordinates(-1,0)},
    {HexagonalCoordinates(0,-1),HexagonalCoordinates(-1,0),HexagonalCoordinates(-1,1)},
    {HexagonalCoordinates(-1,0),HexagonalCoordinates(-1,1)},
    {HexagonalCoordinates(-1,0),HexagonalCoordinates(-1,1),HexagonalCoordinates(0,1)},
    {HexagonalCoordinates(-1,1),HexagonalCoordinates(0,1)},
    {HexagonalCoordinates(-1,1),HexagonalCoordinates(0,1),HexagonalCoordinates(1,0)},
    {HexagonalCoordinates(0,1),HexagonalCoordinates(1,0)},
    {HexagonalCoordinates(0,1),HexagonalCoordinates(1,0),HexagonalCoordinates(1,-1)},
    {HexagonalCoordinates(1,0),HexagonalCoordinates(1,-1)},
    {HexagonalCoordinates(1,0),HexagonalCoordinates(1,-1),HexagonalCoordinates(0,-1)},
    {HexagonalCoordinates(1,-1),HexagonalCoordinates(0,-1)}
    ],dtype=object)

def increase_radius(source:HexagonalCoordinates,target:HexagonalCoordinates):
    result:set[HexagonalCoordinates] = set()
    for x in increase_radius_offsets[get_hexes_by_axis(source,target)]:
        tmp:HexagonalCoordinates = x
        result.add(source+tmp)
    return result

increase_or_keep_radius_offsets=  increase_radius_offsets | keep_radius_offsets

def increase_or_keep_radius(source:HexagonalCoordinates,target:HexagonalCoordinates):
    result:set[HexagonalCoordinates] = set()
    for x in increase_or_keep_radius_offsets[get_hexes_by_axis(source,target)]:
        tmp:HexagonalCoordinates = x
        result.add(source+tmp)
    return result

def is_shooting_line_blocked(source:HexagonalCoordinates,target:HexagonalCoordinates,blockages:set[HexagonalCoordinates]):
    if source.x == target.x:
        min_y = min(source.y, target.y)
        max_y = max(source.y, target.y)
        for y in range(min_y+1, max_y):
            if HexagonalCoordinates(source.x, y) in blockages:
                return True
    elif source.y==target.y:
        min_x = min(source.x, target.x)
        max_x = max(source.x, target.x)
        for x in range(min_x+1, max_x):
            if HexagonalCoordinates(x,source.y) in blockages:
                return True
    elif source.z == target.z:
        min_x = min(source.x, target.x)
        max_x = max(source.x, target.x)
        for x in range(min_x+1, max_x):
            if HexagonalCoordinates(x, -1*x-source.z) in blockages:
                return True
    return False
def is_wizard_line_blocked(source:HexagonalCoordinates,target:HexagonalCoordinates,blockages:set[HexagonalCoordinates],demons:set[HexagonalCoordinates]):
    wizard_range = 5
    if source.x == target.x:
        if source.y>target.y:
            check_for_demons_y = source.y-wizard_range
            for y in range(target.y+1, source.y):
                if HexagonalCoordinates(source.x, y) in blockages:
                    return True
            for y in range(check_for_demons_y, target.y):
                if HexagonalCoordinates(source.x, y) in demons:
                    return True
        else:
            check_for_demons_y = source.y+wizard_range
            for y in range(source.y+1, target.y):
                if HexagonalCoordinates(source.x, y) in blockages:
                    return True
            for y in range(target.y+1, check_for_demons_y+1):
                if HexagonalCoordinates(source.x, y) in demons:
                    return True
    elif source.y==target.y:
        if source.x>target.x:
            check_for_demons_x = source.x-wizard_range
            for x in range(target.x+1, source.x):
                if HexagonalCoordinates(x, source.y) in blockages:
                    return True
            for x in range(check_for_demons_x, target.x):
                if HexagonalCoordinates(x, source.y) in demons:
                    return True
        else:
            check_for_demons_x = source.x+wizard_range
            for x in range(source.x+1, target.x):
                if HexagonalCoordinates(x, source.y) in blockages:
                    return True
            for x in range(target.x+1, check_for_demons_x+1):
                if HexagonalCoordinates(x, source.y) in demons:
                    return True
    elif source.z == target.z:
        if source.x>target.x:
            check_for_demons_x = source.x-wizard_range
            for x in range(target.x+1, source.x):
                if HexagonalCoordinates(x, -1*x-source.z) in blockages:
                    return True
            for x in range(check_for_demons_x, target.x):
                if HexagonalCoordinates(x, -1*x-source.z) in demons:
                    return True
        else:
            check_for_demons_x = source.x+wizard_range
            for x in range(source.x+1, target.x):
                if HexagonalCoordinates(x, -1*x-source.z) in blockages:
                    return True
            for x in range(target.x+1, check_for_demons_x+1):
                if HexagonalCoordinates(x, -1*x-source.z) in demons:
                    return True
    return False

def is_in_line(source:HexagonalCoordinates,target:HexagonalCoordinates)->bool:
    return source.x == target.x or source.y==target.y or source.z == target.z


class Archer(Demon):
    ARCHER_PERFECT_RADIUS = 3
    def __init__(self, position: HexagonalCoordinates) -> None:
        super().__init__(position)
    def in_archer_radius(self,radius):
        return radius>1 and radius<6
    def get_all_moves(self, terrain: Terrain):
        """remember about deleting spear and stairs moves"""
        player = terrain.player
        radius = hexagonal_distance(self.position,player)
        blockages:set[HexagonalCoordinates] = set(terrain.demons.keys())-{self.position}
        secondary_collisions:set[HexagonalCoordinates] = set()
        if terrain.stairs:
            secondary_collisions.add(terrain.stairs)
        if terrain.spear:
            secondary_collisions.add(terrain.spear)
        if terrain.altar:
            blockages.add(terrain.altar)
        if terrain.fleece:
            blockages.add(terrain.fleece)
        if terrain.portal:
            blockages.add(terrain.portal)
        if is_in_line(self.position,player):
            if self.in_archer_radius(radius):
                if not is_shooting_line_blocked(self.position,player,blockages):
                    return frozenset({Attack(self.position)}) 
        # from now archer cannot shoot
        shooting_line_neighbours = {x for x in hexagonal_neighbors(self.position) if terrain.walkable(x) and x not in blockages and self.in_archer_radius(hexagonal_distance(x,player)) and is_in_line(x,player) and not is_shooting_line_blocked(x,terrain.player,blockages)}
        # from now seondary_collisions are collisions
        all_collisions = secondary_collisions|blockages
        if radius>self.ARCHER_PERFECT_RADIUS:
            a = {x for x in reduce_or_keep_radius(self.position,player) if terrain.walkable(x) and x not in all_collisions }
            resulting_actions = frozenset({Walk(self.position,x) for x in a|shooting_line_neighbours})|{Wait(self.position)}
            return resulting_actions
        elif radius==self.ARCHER_PERFECT_RADIUS:
            a = {x for x in keep_radius(self.position,player) if terrain.walkable(x) and x not in all_collisions }
            resulting_actions = frozenset({Walk(self.position,x) for x in a|shooting_line_neighbours})|{Wait(self.position)}
            return resulting_actions
        else: # radius<self.ARCHER_PERFECT_RADIUS
            a = {x for x in increase_or_keep_radius(self.position,player) if terrain.walkable(x) and x not in all_collisions }
            resulting_actions = frozenset({Walk(self.position,x) for x in a|shooting_line_neighbours})|{Wait(self.position)}
            return resulting_actions

    def get_moves(self, terrain: Terrain, collisions: set[HexagonalCoordinates]):
        player = terrain.player
        radius = hexagonal_distance(self.position,player)
        blockages:set[HexagonalCoordinates] = set(terrain.demons.keys())-{self.position}
        if terrain.altar:
            blockages.add(terrain.altar)
        if terrain.fleece:
            blockages.add(terrain.fleece)
        if terrain.portal:
            blockages.add(terrain.portal)
        real_collisions = blockages | collisions|{player}
        if is_in_line(self.position,player):
            if self.in_archer_radius(radius):
                if not is_shooting_line_blocked(self.position,player,blockages):
                    return frozenset({Attack(self.position)}) 
        secondary_collisions:set[HexagonalCoordinates] = set()
        if terrain.stairs:
            secondary_collisions.add(terrain.stairs)
        if terrain.spear:
            secondary_collisions.add(terrain.spear)
        
        nearest: DefaultDict[int,set[HexagonalCoordinates]] = defaultdict(set)
        secondary_nearest: DefaultDict[int,set[HexagonalCoordinates]] = defaultdict(set)
        for neighbor in hexagonal_neighbors(self.position):
            if terrain.walkable(neighbor):
                if neighbor not in real_collisions:
                    if is_in_line(neighbor,player):
                        dist = hexagonal_distance(neighbor,player)
                        if self.in_archer_radius((dist := hexagonal_distance(neighbor,player))):
                            if not is_shooting_line_blocked(neighbor,terrain.player,blockages):
                                if neighbor not in secondary_collisions:
                                    nearest[abs(dist-self.ARCHER_PERFECT_RADIUS)].add(neighbor)
                                else:
                                    secondary_nearest[abs(dist-self.ARCHER_PERFECT_RADIUS)].add(neighbor)
        if nearest.keys():
            return frozenset({Walk(self.position,y) for y in nearest[min(nearest.keys())]})
    
        if secondary_nearest.keys():
            return frozenset({Walk(self.position,y) for y in secondary_nearest[min(secondary_nearest.keys())]})
        # from now archer doesn't stand on stairs and javelin
        all_collisions = secondary_collisions | real_collisions
        if radius>self.ARCHER_PERFECT_RADIUS:
            if (a := {x for x in reduce_radius(self.position,player) if terrain.walkable(x) and x not in all_collisions}):
                return frozenset({Walk(self.position,y) for y in a})
        elif radius<self.ARCHER_PERFECT_RADIUS:
            if (a := {x for x in increase_radius(self.position,player) if terrain.walkable(x) and x not in all_collisions}):
                return frozenset({Walk(self.position,y) for y in a})
        if (a := {x for x in keep_radius(self.position,player) if terrain.walkable(x) and x not in all_collisions}):
            return frozenset({Walk(self.position,y) for y in a})
        return frozenset({Wait(self.position)})
# class Archer:
#     def get_primary_moves(self, position: HexagonalCoordinates, terrain: Terrain,collisions:set[HexagonalCoordinates]):


#         # if can attack return attack
#         # shoting line - line not blocked by anything to player
#         # if can go to shoting line but not on javelin and stairs
#         # > if radius >3 return move reduce radius
#         # > elif radius <3 return move grow radius
#         # > else move with radius
#         # > return if len()>0
#         # if can go to shoting line
#         # > if radius >3 return move reduce radius
#         # > elif radius <3 return move grow radius
#         # > else move with radius
#         # > return if len()>0
#         # from this moment cannot stand on javelin and stairs
#         # > if radius >3 return move reduce radius
#         # > elif radius <3 return move grow radius
#         # > else move with radius
#         # > return if len()>0
#         # return wait
#         return super().get_primary_moves(position, terrain)

class Wizard(Demon):
    WIZARD_PERFECT_RADIUS = 3
    def __init__(self, position: HexagonalCoordinates,charged:bool) -> None:
        super().__init__(position)
        self.charged:bool = charged
    def in_wizard_radius(self,radius):
        return radius<6
    def get_all_moves(self, terrain: Terrain):
        """remember about deleting spear and stairs moves"""
        player = terrain.player
        radius = hexagonal_distance(self.position,player)
        demons :set[HexagonalCoordinates] = set(terrain.demons.keys())-{self.position}
        blockages:set[HexagonalCoordinates] = set()|demons
        secondary_collisions:set[HexagonalCoordinates] = set()
        if terrain.stairs:
            secondary_collisions.add(terrain.stairs)
        if terrain.spear:
            secondary_collisions.add(terrain.spear)
        if terrain.altar:
            blockages.add(terrain.altar)
        if terrain.fleece:
            blockages.add(terrain.fleece)
        if terrain.portal:
            blockages.add(terrain.portal)

        if is_in_line(self.position,player):
            if self.in_wizard_radius(radius):
                if self.charged:
                    if not is_wizard_line_blocked(self.position,player,blockages,demons):
                        return frozenset({Attack(self.position)}) 
                else:
                    if radius==self.WIZARD_PERFECT_RADIUS:
                        return frozenset({Wait(self.position)})

        # from now archer cannot shoot
        shooting_line_neighbours = {x for x in hexagonal_neighbors(self.position) if terrain.walkable(x) and x not in blockages and self.in_wizard_radius(hexagonal_distance(x,player)) and is_in_line(x,player) and not is_wizard_line_blocked(x,terrain.player,blockages,demons)}
        # from now seondary_collisions are collisions
        all_collisions = blockages|secondary_collisions
        if radius>self.WIZARD_PERFECT_RADIUS:
            a = {x for x in reduce_or_keep_radius(self.position,player) if terrain.walkable(x) and x not in all_collisions }
            resulting_actions = frozenset({Walk(self.position,x) for x in a|shooting_line_neighbours})|{Wait(self.position)}
            return resulting_actions
        elif radius==self.WIZARD_PERFECT_RADIUS:
            a = {x for x in keep_radius(self.position,player) if terrain.walkable(x) and x not in all_collisions }
            resulting_actions = frozenset({Walk(self.position,x) for x in a|shooting_line_neighbours})|{Wait(self.position)}
            return resulting_actions
        else: # radius<self.ARCHER_PERFECT_RADIUS
            a = {x for x in increase_or_keep_radius(self.position,player) if terrain.walkable(x) and x not in all_collisions }
            resulting_actions = frozenset({Walk(self.position,x) for x in a|shooting_line_neighbours})|{Wait(self.position)}
            return resulting_actions

    def get_moves(self, terrain: Terrain, collisions: set[HexagonalCoordinates]):
        player = terrain.player
        radius = hexagonal_distance(self.position,player)
        demons :set[HexagonalCoordinates] = set(terrain.demons.keys())-{self.position}
        blockages:set[HexagonalCoordinates] = set()|demons
        if terrain.altar:
            blockages.add(terrain.altar)
        if terrain.fleece:
            blockages.add(terrain.fleece)
        if terrain.portal:
            blockages.add(terrain.portal)
        real_collisions = blockages | collisions
        if is_in_line(self.position,player):
            if self.in_wizard_radius(radius):
                if self.charged:
                    if not is_wizard_line_blocked(self.position,player,blockages,demons):
                        return frozenset({Attack(self.position)}) 
                else:
                    if radius==self.WIZARD_PERFECT_RADIUS:
                        return frozenset({Wait(self.position)})
        secondary_collisions:set[HexagonalCoordinates] = set()
        if terrain.stairs:
            secondary_collisions.add(terrain.stairs)
        if terrain.spear:
            secondary_collisions.add(terrain.spear)
        
        nearest: DefaultDict[int,set[HexagonalCoordinates]] = defaultdict(set)
        secondary_nearest: DefaultDict[int,set[HexagonalCoordinates]] = defaultdict(set)
        for neighbor in hexagonal_neighbors(self.position):
            if terrain.walkable(neighbor):
                if neighbor not in real_collisions:
                    if is_in_line(neighbor,player):
                        dist = hexagonal_distance(neighbor,player)
                        if self.in_wizard_radius((dist := hexagonal_distance(neighbor,player))):
                            if not is_wizard_line_blocked(neighbor,terrain.player,blockages,demons):
                                if neighbor not in secondary_collisions:
                                    nearest[abs(dist-self.WIZARD_PERFECT_RADIUS)].add(neighbor)
                                else:
                                    secondary_nearest[abs(dist-self.WIZARD_PERFECT_RADIUS)].add(neighbor)
        if nearest.keys():
            return frozenset({Walk(self.position,y) for y in nearest[min(nearest.keys())]})
    
        if secondary_nearest.keys():
            return frozenset({Walk(self.position,y) for y in secondary_nearest[min(secondary_nearest.keys())]})
        # from now archer doesn't stand on stairs and javelin
        all_collisions = secondary_collisions | real_collisions
        if radius>self.WIZARD_PERFECT_RADIUS:
            if (a := {x for x in reduce_radius(self.position,player) if terrain.walkable(x) and x not in all_collisions}):
                return frozenset({Walk(self.position,y) for y in a})
        elif radius<self.WIZARD_PERFECT_RADIUS:
            if (a := {x for x in increase_radius(self.position,player) if terrain.walkable(x) and x not in all_collisions}):
                return frozenset({Walk(self.position,y) for y in a})
        if (a := {x for x in keep_radius(self.position,player) if terrain.walkable(x) and x not in all_collisions}):
            return frozenset({Walk(self.position,y) for y in a})
        return frozenset({Wait(self.position)})


class Demolitionist(Demon):
    DEMOLITIONIST_PERFECT_RADIUS = 3
    DEMOLITIONIST_RADIUS = 3
    def __init__(self, position: HexagonalCoordinates,cooldown:int) -> None:
        super().__init__(position)
        self.cooldown:int = cooldown
    def in_radius(self,radius):
        return radius<5
    def get_all_moves(self, terrain: Terrain):
        """remember about deleting spear and stairs moves"""
        player = terrain.player
        radius = hexagonal_distance(self.position,player)
        demons :set[HexagonalCoordinates] = set(terrain.demons.keys())
        blockages:set[HexagonalCoordinates] = set()|demons
        secondary_collisions:set[HexagonalCoordinates] = set()
        if terrain.stairs:
            secondary_collisions.add(terrain.stairs)
        if terrain.spear:
            secondary_collisions.add(terrain.spear)
        if terrain.altar:
            blockages.add(terrain.altar)
        if terrain.fleece:
            blockages.add(terrain.fleece)
        if terrain.portal:
            blockages.add(terrain.portal)

        # attack logic
        if not self.cooldown:
            if self.in_radius(radius):
                bomb_destinations = {destination for destination in hexagonal_neighbors(player) if terrain.walkable(destination) and destination not in blockages and hexagonal_distance(self.position,destination)<=self.DEMOLITIONIST_RADIUS and all(in_explosion_range not in demons for in_explosion_range in hexagonal_neighbors(destination))}
                if bomb_destinations:
                    return frozenset({Bomb(self.position,destination) for destination in bomb_destinations})

        # from now archer cannot shoot
        # from now seondary_collisions are collisions
        all_collisions = blockages|secondary_collisions
        if radius>self.DEMOLITIONIST_PERFECT_RADIUS:
            a = {x for x in reduce_or_keep_radius(self.position,player) if terrain.walkable(x) and x not in all_collisions }
            resulting_actions = frozenset({Walk(self.position,x) for x in a})|{Wait(self.position)}
            return resulting_actions
        elif radius==self.DEMOLITIONIST_PERFECT_RADIUS:
            a = {x for x in keep_radius(self.position,player) if terrain.walkable(x) and x not in all_collisions }
            resulting_actions = frozenset({Walk(self.position,x) for x in a})|{Wait(self.position)}
            return resulting_actions
        else: # radius<self.ARCHER_PERFECT_RADIUS
            a = {x for x in increase_or_keep_radius(self.position,player) if terrain.walkable(x) and x not in all_collisions }
            resulting_actions = frozenset({Walk(self.position,x) for x in a})|{Wait(self.position)}
            return resulting_actions

    def get_moves(self, terrain: Terrain, collisions: set[HexagonalCoordinates]):
        player = terrain.player
        radius = hexagonal_distance(self.position,player)
        demons :set[HexagonalCoordinates] = set(terrain.demons.keys())-{self.position}
        blockages:set[HexagonalCoordinates] = set()|demons
        if terrain.altar:
            blockages.add(terrain.altar)
        if terrain.fleece:
            blockages.add(terrain.fleece)
        if terrain.portal:
            blockages.add(terrain.portal)
        if not self.cooldown:
            if self.in_radius(radius):
                bomb_destinations = {destination for destination in hexagonal_neighbors(player) if terrain.walkable(destination) and destination not in blockages and hexagonal_distance(self.position,destination)<=self.DEMOLITIONIST_RADIUS and all(in_explosion_range not in demons for in_explosion_range in hexagonal_neighbors(destination))}
                if bomb_destinations:
                    return frozenset({Bomb(self.position,destination) for destination in bomb_destinations})
        secondary_collisions:set[HexagonalCoordinates] = set()
        if terrain.stairs:
            secondary_collisions.add(terrain.stairs)
        if terrain.spear:
            secondary_collisions.add(terrain.spear)
        
        # from now archer doesn't stand on stairs and javelin
        all_collisions = secondary_collisions | blockages | collisions
        if radius>self.DEMOLITIONIST_PERFECT_RADIUS:
            if (a := {x for x in reduce_radius(self.position,player) if terrain.walkable(x) and x not in all_collisions}):
                return frozenset({Walk(self.position,y) for y in a})
        elif radius<self.DEMOLITIONIST_PERFECT_RADIUS:
            if (a := {x for x in increase_radius(self.position,player) if terrain.walkable(x) and x not in all_collisions}):
                return frozenset({Walk(self.position,y) for y in a})
        if (a := {x for x in keep_radius(self.position,player) if terrain.walkable(x) and x not in all_collisions}):
            return frozenset({Walk(self.position,y) for y in a})
        return frozenset({Wait(self.position)})

T = TypeVar('T')


def try_get_dag(combination: Tuple[Tuple[T, frozenset[T]]]):
    """check if combination is correct"""
    dag = nx.DiGraph()
    for base, destinations in combination:
        for destination in destinations:
            if dag.has_node(base) and destination in nx.ancestors(dag, base):
                return None
            dag.add_edge(base, destination)
    return dag


def get_all_correct_dags(possibilities: set[frozenset[Tuple[T, frozenset[T]]]]):
    """yield all correct combination of inequalities"""
    for option in itertools.product(*possibilities):  # use frozenset
        if (dag := try_get_dag(option)):
            yield dag


def split(data: frozenset[T]) -> frozenset[Tuple[T, frozenset[T]]]:
    return frozenset({(item, data.difference({item})) for item in data})


def get_all_possible_moves(pre_game_state: hoplite.game.state.GameState, player_move: hoplite.game.moves.PlayerMove):
    """get all game states after player moves"""
    game_state = player_move.apply(pre_game_state)
    terrain = game_state.terrain
    # 0) map all demons
    # 1) enumerate all demons ???
    # 2) get all moves and collisions
    # 3) get all orders
    # 4) calculate them
    # 5) orders by states
    demons = {demon_mapper(demon, coords)
              for coords, demon in terrain.demons.items()}
    enumerated_demons = {num: demon for num, demon in enumerate(demons)}
    demons_by_positions = {demon.position: (
        num, demon) for num, demon in enumerated_demons.items()}

    actions_by_destination: DefaultDict[HexagonalCoordinates,
                                        set[Action]] = defaultdict(set)
    for demon in demons:
        for action in demon.get_all_moves(terrain):
            actions_by_destination[action.destination].add(action)

    conflicts = {split(frozenset({demons_by_positions[action.source][0] for action in actions})) for _,
                 actions in actions_by_destination.items() if len(actions) > 1}
    all_combinations: set[frozenset[Action]] = set(frozenset())
    if not conflicts:
        all_combinations = {
            frozenset(i) for i in itertools.product(*{demon.get_moves(terrain, set()) for demon in demons})}
    for dag in (get_all_correct_dags(conflicts) or [nx.DiGraph()]):
        order_of_demons: list[int] = list(nx.topological_sort(dag))
        ordered_demons_moves: set[Tuple[frozenset[HexagonalCoordinates], frozenset[Action]]] = {
            (frozenset(), frozenset())}
        for demon_enumerated in order_of_demons:
            ordered_demons_moves = {(collisions.union({demon_move.destination}), moves.union({demon_move})) for collisions,
                                    moves in ordered_demons_moves for demon_move in enumerated_demons[demon_enumerated].get_moves(terrain, collisions)}

            # return all states from known order.
        unordered_demons = {enumerated_demons[demon_number].get_moves(terrain, set(
        )) for demon_number in set(enumerated_demons.keys()).difference(order_of_demons)}
        unordered_demons_moves: set[frozenset[Action]] = {
            frozenset(i) for i in itertools.product(*unordered_demons)}
        all_combinations.update({unordered_demons_moves_set.union(ordered_demons_moves_set)
                                for unordered_demons_moves_set in unordered_demons_moves for _, ordered_demons_moves_set in ordered_demons_moves})
    all_combination_combined: set[Action] = set().union(*all_combinations)
    return all_combination_combined,apply_actions(game_state,all_combinations)


# %%


class Colors:
    GREEN = [0., 1., 0., 1.]
    BLUE = [.2, .6, 1., 1.]
    ORANGE = [1, .6, .1, 1.]
    RED = [1., 0., 0., 1.]
    BLACK = [0.,0.,0.,0.]


def circle(array: ndarray, position: HexagonalCoordinates, color: list[float], diameter: int = 50, corner: int = 500):
    coordinates = hoplite.actuator.hexagonal_to_pixels(position)
    radius = diameter // 2
    for x in range(diameter):
        for y in range(diameter):
            if (x - radius) ** 2 + (y - radius) ** 2 >= corner:
                continue
            array[
                coordinates[1] + y - radius,
                coordinates[0] + x - radius
            ] = color[:]


def trapez(y, y0, w):
    return np.clip(np.minimum(y+1+w/2-y0, -y+1+w/2+y0), 0, 1)


def weighted_line(r0: int, c0: int, r1: int, c1: int, w: int, rmin: int = 0, rmax=np.inf):
    # The algorithm below works fine if c1 >= c0 and c1-c0 >= abs(r1-r0).
    # If either of these cases are violated, do some switches.
    if abs(c1-c0) < abs(r1-r0):
        # Switch x and y, and switch again when returning.
        xx, yy, val = weighted_line(c0, r0, c1, r1, w, rmin=rmin, rmax=rmax)
        return (yy, xx, val)

    # At this point we know that the distance in columns (x) is greater
    # than that in rows (y). Possibly one more switch if c0 > c1.
    if c0 > c1:
        return weighted_line(r1, c1, r0, c0, w, rmin=rmin, rmax=rmax)

    # The following is now always < 1 in abs
    slope = (r1-r0) / (c1-c0)

    # Adjust weight by the slope
    w *= np.sqrt(1+np.abs(slope)) / 2

    # We write y as a function of x, because the slope is always <= 1
    # (in absolute value)
    x = np.arange(c0, c1+1, dtype=float)
    y = x * slope + (c1*r0-c0*r1) / (c1-c0)

    # Now instead of 2 values for y, we have 2*np.ceil(w/2).
    # All values are 1 except the upmost and bottommost.
    thickness = np.ceil(w/2)
    yy = (np.floor(y).reshape(-1, 1) +
          np.arange(-thickness-1, thickness+2).reshape(1, -1))
    xx = np.repeat(x, yy.shape[1])
    vals = trapez(yy, y.reshape(-1, 1), w).flatten()

    yy = yy.flatten()

    # Exclude useless parts and those outside of the interval
    # to avoid parts outside of the picture
    mask = np.logical_and.reduce((yy >= rmin, yy < rmax, vals > 0))

    return (yy[mask].astype(int), xx[mask].astype(int), vals[mask])


def line(img: ndarray, source: HexagonalCoordinates, destination: HexagonalCoordinates, weight: int = 20):
    x_source, y_source = hoplite.actuator.hexagonal_to_pixels(source)
    x_destination, y_destination = hoplite.actuator.hexagonal_to_pixels(
        destination)
    ys, xs, value = weighted_line(
        x_source, y_source, x_destination, y_destination, weight)
    for y, x, modifier in zip(ys, xs, value):
        img[x, y] = np.array([1, 0, 0, 1.]) * modifier


def transform(prev_state: hoplite.game.state.GameState, next_state: hoplite.game.state.GameState, possible_moves: set[Action], img_path: str):
    screenshot = matplotlib.image.imread(img_path)
    for action in possible_moves:
        if isinstance(action, Wait):
            circle(screenshot, action.source, Colors.GREEN)
        elif isinstance(action, Walk):
            line(screenshot, action.source, action.destination)
        elif isinstance(action, Attack):
            circle(screenshot, action.source, Colors.BLUE, diameter=25)
        elif isinstance(action, Bomb):
            circle(screenshot, action.source, Colors.RED, diameter=25)
            circle(screenshot, action.destination, Colors.RED, diameter=25)
    demons_that_moved = set(map(lambda action: action.source, possible_moves))
    for dead in {x for x in prev_state.terrain.demons.keys() if x not in demons_that_moved}:
        circle(screenshot, dead, Colors.BLACK, diameter=75)
    circle(screenshot, next_state.terrain.player, Colors.BLUE, diameter=75)
    return screenshot
# %%


def is_altar_use(line: str): return line.split("\t")[1] != "move"
def get_level(line: str): return line.split("\t")[2].split(";")[0]


def is_same_level(line1: str, line2: str): return get_level(
    line1) == get_level(line2)


def get_pairs(lines: list[str]):
    last_line = None
    for line in lines:
        if is_altar_use(line):
            continue
        if not last_line:
            last_line = line
            continue
        if not is_same_level(last_line, line):
            last_line = line
            continue
        yield (last_line, line)
        last_line = line
# %%


def parse(states: Iterator[Tuple[str, str]]):
    for prev_line, next_line in states:
        _turn = int(prev_line.split("\t")[0])
        _prev_state = hoplite.game.state.GameState.from_string(
            prev_line.split("\t")[2])
        _next_state = hoplite.game.state.GameState.from_string(
            next_line.split("\t")[2])
        _move = hoplite.game.moves.PlayerMove.from_string(
            prev_line.split("\t")[3])
        # cause there is incorrect logic to bash moves
        if isinstance(_move, hoplite.game.moves.WalkMove):
            _after_player_move_state = _move.apply(_prev_state)
            if len(_after_player_move_state.terrain.demons.items()) > 0:
                yield _turn, _prev_state, _next_state, _move
# %%


def ifn(folder: str, turn: int):
    return os.path.join(
        folder,
        str(turn).rjust(3, "0") + ".png"
    )


def ofn(folder: str, turn: int, error: bool):
    return os.path.join(
        OUTPUT_DIRECTORY,
        {
            True: "fail",
            False: "success"
        }[error],
        "%s-%s.png" % (
            os.path.basename(folder),
            str(turn).rjust(3, "0")
        )
    )


# %%
for suffix in ["fail", "success"]:
    os.makedirs(
        os.path.join(OUTPUT_DIRECTORY, suffix),
        exist_ok=True
    )
# %%
limit = 20

for folder in glob.glob(os.path.join(RECORDINGS_FOLDER, "*")):
    i = 0
    filename = os.path.join(folder, LOG_FILENAME)
    print(filename)
    try:
        with open(filename, encoding='utf-8') as file:
            lines = file.readlines()
    except FileNotFoundError:
        continue
    for turn, prev_state, next_state, move in parse(get_pairs(lines)):
        # predict state
        # check state
        possible_moves,next_states = get_all_possible_moves(prev_state, move)
        screenshot = transform(
            prev_state,
            next_state,
            possible_moves,
            ifn(folder, turn)
        )
        if i > limit:
            break
        i += 1
        error = next_state not in next_states
        matplotlib.image.imsave(
            ofn(folder, turn, error),
            screenshot
        )

# %%
